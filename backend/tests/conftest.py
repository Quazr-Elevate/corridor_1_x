"""Test harness: the real ASGI app against a throwaway SQLite DB.

Environment is set BEFORE importing ``app`` so Settings/engine pick it up
(env vars override backend/.env).
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import bcrypt
import pytest
import pytest_asyncio

# Cheap bcrypt in tests (production uses the library default cost).
_orig_gensalt = bcrypt.gensalt
bcrypt.gensalt = lambda rounds=4, prefix=b"2b": _orig_gensalt(4, prefix)  # type: ignore[assignment]

_TMP = Path(tempfile.mkdtemp(prefix="cor1x-tests-"))
ADMIN_EMAIL = "admin@cor1x.test"
ADMIN_PASSWORD = "admin-pass-123"

os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP / 'test.db'}",
        "DEBUG": "false",
        "CROSS_SITE_COOKIES": "false",
        "SESSION_SECRET": "test-session-secret",
        # Two encryption key versions (2 = current) to exercise rotation.
        "KYB_ENC_KEYS": "1:" + base64.b64encode(b"k" * 32).decode() + ",2:" + base64.b64encode(b"K" * 32).decode(),
        "KYB_HASH_KEY": base64.b64encode(b"h" * 32).decode(),
        "ADMIN_SESSION_SECRET": "test-admin-secret",
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "ADMIN_PASSWORD_HASH": bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode(),
        "EMAIL_PROVIDER": "console",
        "EMAIL_OUTBOX_DIR": str(_TMP / "outbox"),
        "SMS_PROVIDER": "console",
        "SMS_OUTBOX_DIR": str(_TMP / "outbox" / "sms"),
        "STORAGE_BACKEND": "local",
        "STORAGE_DIR": str(_TMP / "uploads"),
        "LOOKUPS_STUB": "false",
        # No network in tests: fixed rates, no background refresh.
        "FX_ENABLED": "false",
        "FX_PROVIDERS": "static",
        "FX_SUPPORTED_CURRENCIES": "INR,AED,USD",
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_TRUSTED_PROXIES": "0",
        "LOG_LEVEL": "WARNING",
        "CORS_ORIGINS": "http://localhost:3000",
        "FRONTEND_BASE_URL": "http://localhost:3000",
    }
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import delete, update  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.db import SessionLocal, engine  # noqa: E402
from app.integrations.email import get_provider  # noqa: E402
from app.main import app as asgi_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.business import Business, BusinessStatus  # noqa: E402
from app.models.user import User  # noqa: E402
from app.ratelimit import get_limiter  # noqa: E402


def pytest_collection_modifyitems(items):
    # One event loop for the whole session (the engine's pool is global).
    marker = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(marker, append=False)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


async def _seed(conn) -> None:
    """Default countries + KYB document types (what migrations 0021/0023 seed)."""
    from app.models.country import Country
    from app.models.kyb_document_type import KybDocumentType
    from app.modules.verification.seed import default_country_rows, default_rows

    await conn.execute(Country.__table__.insert(), default_country_rows())
    await conn.execute(KybDocumentType.__table__.insert(), default_rows())


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _seed(conn)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _clean():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))
        await _seed(conn)
    await get_limiter().reset()
    get_provider().sent.clear()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi_app), base_url="http://testserver")


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with _client() as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def make_client():
    clients: list[httpx.AsyncClient] = []

    def _make() -> httpx.AsyncClient:
        c = _client()
        clients.append(c)
        return c

    yield _make
    for c in clients:
        await c.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def admin_client(make_client):
    c = make_client()
    r = await c.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return c


# ── helpers ──────────────────────────────────────────────────────────


def sent_emails(to: str | None = None):
    msgs = list(get_provider().sent)
    return [m for m in msgs if to is None or m.to == to]


def code_from_email(to: str) -> str:
    msg = [m for m in sent_emails(to) if "verification code" in m.subject][-1]
    match = re.search(r"\b(\d{6})\b", msg.text)
    assert match, msg.text
    return match.group(1)


async def signup_and_login(
    c: httpx.AsyncClient,
    email: str,
    *,
    password: str = "Sup3r-secret!",
    full_name: str = "Asha Rao",
    company_name: str | None = None,
    position: str | None = None,
) -> dict:
    """Code → verify → complete; the client ends up signed in."""
    r = await c.post("/auth/signup/code", json={"email": email})
    assert r.status_code == 200, r.text
    r = await c.post("/auth/signup/verify", json={"email": email, "code": code_from_email(email.lower())})
    assert r.status_code == 200, r.text
    body = {
        "email": email,
        "fullName": full_name,
        "companyName": company_name or f"{email.split('@')[0]} {email.split('@')[1].split('.')[0]} Trading",
        "password": password,
        "acceptTerms": True,
    }
    if position:
        body["position"] = position
    r = await c.post("/auth/signup/complete", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def fill_mandatory(c: httpx.AsyncClient, *, n: int = 1) -> None:
    """Everything KYB submission needs (India): company name + address +
    GSTIN + PAN entries, plus the older Passport sections."""
    r = await c.post(
        "/onboarding/company",
        json={
            "legalName": f"Acme Agro {n} Pvt Ltd",
            "industry": "Rice",
            "operatingCountries": ["IN"],
            "addressLine": f"{n} Market Road",
            "city": "Karnal",
            "country": "IN",
        },
    )
    assert r.status_code == 200, r.text
    r = await c.post(
        "/onboarding/contact",
        json={"fullName": "Asha Rao", "phone": f"+91 98765 0000{n}", "position": "Director"},
    )
    assert r.status_code == 200, r.text
    r = await c.post("/onboarding/business", json={"tradePosition": "both"})
    assert r.status_code == 200, r.text
    types = {t["code"]: t["id"] for t in (await c.get("/kyb/document-types")).json()}
    for code, value in (("gstin", f"{n:02d}AAAAA{n:04d}A1Z5"), ("pan", f"AAAAA{n:04d}A")):
        r = await c.post("/me/verification-docs", data={"documentTypeId": types[code], "value": value})
        assert r.status_code == 201, r.text


async def set_status(user_id: str, status: BusinessStatus) -> None:
    """Force the user's business into ``status`` (consistent with the CHECKs)."""
    import uuid

    from app.core.time import utcnow

    async with SessionLocal() as db:
        user = await db.get(User, uuid.UUID(user_id))
        now = utcnow()
        values = {"verification_status": status}
        if status != BusinessStatus.draft:
            values["verification_submitted_at"] = now
        if status == BusinessStatus.verified:
            values["verified_at"] = now
        if status == BusinessStatus.rejected:
            values["verification_rejected_reason"] = "test"
        await db.execute(update(Business).where(Business.id == user.business_id).values(**values))
        await db.commit()


def png_bytes(size: int = 4) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = zlib.compress((b"\x00" + b"\x10\x80\x20" * size) * size)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
