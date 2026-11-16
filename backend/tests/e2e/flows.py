"""Journey helpers for the end-to-end suite.

These compose the *real* HTTP calls a browser makes, in the order the
product makes them, so an E2E test reads like the user story it covers.
Everything builds on the fixtures in ``tests/conftest.py`` (real ASGI app,
throwaway SQLite DB, console email, static FX, temp storage).

Scenario IDs (``E2E-…``) are documented in ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

import httpx
from conftest import Counter, fill_mandatory, png_bytes, sent_emails, signup_and_login

__all__ = ["Counter"]

# A tiny real PDF — passes the magic-byte sniffer for KYB documents.
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

PASSWORD = "Sup3r-secret!"


def email_for(prefix: str, *, domain: str = "kaverifoods.in") -> str:
    """A work email nobody else in the run uses (no free-mail domains)."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@{domain}"


@dataclass
class Trader:
    """One signed-in trader: their client, ids and what they own."""

    client: httpx.AsyncClient
    email: str
    user_id: str
    business_id: str
    n: int
    products: list[str] = field(default_factory=list)


async def sign_up(make_client, counter: Counter, *, prefix: str = "t", domain: str = "kaverifoods.in") -> Trader:
    """E2E step: land on /signup, prove the email, set a password.

    Ends with the browser holding a session cookie and the business in
    ``draft``.
    """
    c = make_client()
    email = email_for(prefix, domain=domain)
    body = await signup_and_login(c, email, password=PASSWORD)
    return Trader(
        client=c,
        email=email.lower(),
        user_id=body["userId"],
        business_id=body["businessId"],
        n=counter.next(),
    )


async def fill_passport(trader: Trader) -> None:
    """E2E step: fill every mandatory Passport field + required KYB docs."""
    await fill_mandatory(trader.client, n=trader.n)


async def submit(trader: Trader) -> dict:
    """E2E step: press "Send for verification"."""
    r = await trader.client.post("/me/submit-verification")
    assert r.status_code == 200, r.text
    return r.json()


async def admin_verify(admin: httpx.AsyncClient, trader: Trader) -> dict:
    r = await admin.post(f"/admin/users/{trader.user_id}/verify")
    assert r.status_code == 200, r.text
    return r.json()


async def admin_reject(
    admin: httpx.AsyncClient, trader: Trader, *, reason: str = "Document unreadable.", items: list[str] | None = None
) -> dict:
    """E2E step: ops rejects the business, naming at least one failed item
    (``failedItems`` is mandatory — a rejection always says what to fix)."""
    body = {"reason": reason, "failedItems": items if items is not None else ["addressLine"]}
    r = await admin.post(f"/admin/users/{trader.user_id}/reject", json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def verified_trader(make_client, admin: httpx.AsyncClient, counter: Counter, *, prefix: str = "t",
                          domain: str = "kaverifoods.in") -> Trader:
    """The whole onboarding journey in one call: signup → Passport → KYB →
    submit → admin approval. Ends ``verified``."""
    trader = await sign_up(make_client, counter, prefix=prefix, domain=domain)
    await fill_passport(trader)
    await submit(trader)
    await admin_verify(admin, trader)
    return trader


async def photo(trader: Trader) -> str:
    r = await trader.client.post("/products/upload-photo", files={"file": ("lot.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["url"]


def product_body(photos: list[str], **over) -> dict:
    body = {
        "name": "1121 Steam Basmati",
        "category": "Rice",
        "variety": "1121",
        "originState": "Haryana",
        "packaging": "Jute",
        "quantity": "500",
        "unit": "MT",
        "moq": "25",
        "pricePerUnit": "72.50",
        "currency": "INR",
        "description": "Aromatic long grain, sortex clean.",
        "photos": photos,
    }
    body.update(over)
    return body


async def list_lot(trader: Trader, **over) -> dict:
    """E2E step: publish one listing (uploads its photo first)."""
    r = await trader.client.post("/products", json=product_body([await photo(trader)], **over))
    assert r.status_code == 201, r.text
    lot = r.json()
    trader.products.append(lot["id"])
    return lot


def reset_code(email: str) -> str:
    """The 6-digit code from the last password-reset email to ``email``."""
    msg = [m for m in sent_emails(email) if "password reset code" in m.subject][-1]
    match = re.search(r"\b(\d{6})\b", msg.text)
    assert match, msg.text
    return match.group(1)


async def reset_password(c: httpx.AsyncClient, email: str, new_password: str) -> None:
    """E2E step: forgot password → emailed code → new password."""
    r = await c.post("/auth/password/forgot", json={"email": email})
    assert r.status_code == 200, r.text
    r = await c.post(
        "/auth/password/reset",
        json={"email": email, "code": reset_code(email), "newPassword": new_password},
    )
    assert r.status_code == 200, r.text


async def login(c: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await c.post("/auth/login", json={"email": email, "password": password})
