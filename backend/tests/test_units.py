"""Unit tests for the reusable modules (no HTTP)."""
from __future__ import annotations

import httpx
import pytest

from app.integrations._retry import TransientError, retry_async
from app.integrations.email import EmailConfig, EmailDeliveryError, EmailMessage
from app.integrations.email.providers import ResendProvider
from app.integrations.lookups import PincodeError, PincodeLookup, PincodeServiceError
from app.integrations.sms import ConsoleSmsProvider, SmsConfig, normalize_msisdn
from app.integrations.storage import InvalidKey, LocalStorage, ObjectNotFound, detect
from app.integrations.storage.filetypes import JPEG, PDF, PNG, WEBP
from app.modules.lookups.router import get_pincode_lookup
from app.ratelimit import MemoryRateLimitBackend, RateLimiter, RateLimitExceeded, RateLimitRule
from app.shared.normalize import normalize_legal_name, normalize_phone, normalize_website


# ── rate limiter ─────────────────────────────────────────────────────


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


async def test_sliding_window_rate_limiter():
    clock = FakeClock()
    limiter = RateLimiter(MemoryRateLimitBackend(clock=clock))
    rule = RateLimitRule("t", limit=3, window_sec=60)
    for _ in range(3):
        await limiter.check(rule, "Key")
    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check(rule, "key")  # identifiers are case-insensitive
    assert exc.value.retry_after == 60
    clock.t += 30
    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check(rule, "key")
    assert exc.value.retry_after == 30
    clock.t += 31  # first hits slide out of the window
    await limiter.check(rule, "key")
    await limiter.check(rule, "other")  # separate budget
    await limiter.check(rule, None)  # unknown identifier is not limited


async def test_rate_limiter_multiplier_and_disable():
    rule = RateLimitRule("t", limit=1, window_sec=60)
    relaxed = RateLimiter(MemoryRateLimitBackend(), multiplier=3)
    for _ in range(3):
        await relaxed.check(rule, "k")
    with pytest.raises(RateLimitExceeded):
        await relaxed.check(rule, "k")
    off = RateLimiter(MemoryRateLimitBackend(), enabled=False)
    for _ in range(10):
        await off.check(rule, "k")


# ── sms ──────────────────────────────────────────────────────────────


async def test_console_sms_provider(tmp_path):
    sms = ConsoleSmsProvider(SmsConfig(outbox_dir=tmp_path))
    await sms.send_sms("98765 43210", "hello")
    assert sms.sent[-1].to == "919876543210"
    assert list(tmp_path.glob("*.txt"))

    result = await sms.send_otp("+91 98765-43210")
    assert result.to == "919876543210" and result.request_id
    code = sms.last_code_for("9876543210")
    assert code and len(code) == 6
    assert await sms.verify_otp("9876543210", "000000" if code != "000000" else "111111") is False
    assert await sms.verify_otp("+919876543210", code) is True
    assert await sms.verify_otp("+919876543210", code) is False  # single use


def test_normalize_msisdn():
    assert normalize_msisdn("09876543210") == "919876543210"
    assert normalize_msisdn("+1 (415) 555-0100") == "14155550100"
    assert normalize_msisdn("0044 20 7946 0000") == "442079460000"


# ── storage ──────────────────────────────────────────────────────────


async def test_local_storage(tmp_path):
    store = LocalStorage(tmp_path)
    obj = await store.save(b"data", "products/abc.png", "image/png")
    assert obj.size == 4
    assert await store.exists("products/abc.png")
    assert await store.open("products/abc.png") == b"data"
    await store.delete("products/abc.png")
    assert not await store.exists("products/abc.png")
    await store.delete("products/abc.png")  # idempotent
    with pytest.raises(ObjectNotFound):
        await store.open("products/abc.png")
    for bad in ("../x", "/etc/passwd", "a/../../x", "a//b", ".hidden", "a\\b"):
        with pytest.raises(InvalidKey):
            await store.save(b"x", bad, "text/plain")
        assert await store.exists(bad) is False


def test_magic_bytes():
    assert detect(b"%PDF-1.7 ...") is PDF
    assert detect(b"\xff\xd8\xff\xe0....") is JPEG
    assert detect(b"\x89PNG\r\n\x1a\n....") is PNG
    assert detect(b"RIFF\x00\x00\x00\x00WEBPVP8 ") is WEBP
    assert detect(b"<html>") is None
    assert detect(b"") is None


def test_normalizers():
    assert normalize_phone("+91 (98765) 43-210") == "+919876543210"
    assert normalize_legal_name("  Kaveri   Foods PVT ltd ") == "kaveri foods pvt ltd"
    assert normalize_website("HTTPS://www.Kaveri.in/?utm=1") == "kaveri.in"
    assert normalize_website("facebook.com/acme/") == "facebook.com/acme"
    assert normalize_website("  ") is None


# ── email retry ──────────────────────────────────────────────────────


async def test_resend_retries_transient_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, json={"id": "x"})

    cfg = EmailConfig(provider="resend", api_key="re_test", from_address="a@b.c", max_attempts=3)
    provider = ResendProvider(cfg, transport=httpx.MockTransport(handler))
    await provider.send(EmailMessage(to="x@y.z", subject="s", html="<p>h</p>", text="h"))
    assert len(calls) == 2
    assert calls[0].headers["Authorization"] == "Bearer re_test"


async def test_resend_does_not_retry_client_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(422, json={"message": "bad from"})

    cfg = EmailConfig(provider="resend", api_key="re_test", from_address="a@b.c", max_attempts=3)
    provider = ResendProvider(cfg, transport=httpx.MockTransport(handler))
    with pytest.raises(EmailDeliveryError):
        await provider.send(EmailMessage(to="x@y.z", subject="s", html="h", text="h"))
    assert len(calls) == 1


async def test_retry_gives_up():
    attempts = 0

    async def boom():
        nonlocal attempts
        attempts += 1
        raise TransientError("nope")

    with pytest.raises(TransientError):
        await retry_async(boom, attempts=2, base_delay=0.001)
    assert attempts == 2


# ── lookups ──────────────────────────────────────────────────────────


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("unreachable", request=request)


async def test_pincode_lookup_outage_raises():
    lookup = PincodeLookup(transport=httpx.MockTransport(_down))
    with pytest.raises(PincodeServiceError):
        await lookup.lookup("560001")
    with pytest.raises(PincodeError):
        await lookup.lookup("12ab")
    stub = await PincodeLookup(stub=True).lookup("560001")
    assert stub.city == "Mumbai"


async def test_pincode_endpoint_outage_is_502(client):
    from app.main import app

    app.dependency_overrides[get_pincode_lookup] = lambda: PincodeLookup(transport=httpx.MockTransport(_down))
    try:
        r = await client.get("/pincode/560001")
        assert r.status_code == 502
        assert r.json()["detail"] == "Pincode service unavailable, enter city/state manually"
        assert (await client.get("/pincode/abc")).status_code == 404
    finally:
        app.dependency_overrides.clear()


async def test_pincode_endpoint_success(client):
    from app.main import app

    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"Status": "Success", "PostOffice": [{"Name": "Bangalore GPO", "District": "Bangalore", "State": "Karnataka"}]}],
        )

    app.dependency_overrides[get_pincode_lookup] = lambda: PincodeLookup(transport=httpx.MockTransport(ok))
    try:
        r = await client.get("/pincode/560001")
        assert r.status_code == 200
        assert r.json() == {"pincode": "560001", "city": "Bangalore GPO", "district": "Bangalore", "state": "Karnataka"}
    finally:
        app.dependency_overrides.clear()


# ── notifications / sessions ─────────────────────────────────────────


def test_email_templates_escape_html():
    from app.notifications import render

    html, text = render(
        "verification_rejected", first_name="<b>x</b>", reason="<script>alert(1)</script>", account_url="http://a"
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in text  # plain-text part is literal


async def test_legacy_signed_cookie_is_rejected(client):
    """Pre-0024 signed cookies (``{"uid", "sv"}``) no longer sign anyone in —
    sessions are server-side now."""
    from itsdangerous import URLSafeTimedSerializer

    from app.core.config import settings
    from app.core.security import SESSION_COOKIE
    from conftest import signup_and_login

    body = await signup_and_login(client, "legacy@kaverifoods.in")
    legacy = URLSafeTimedSerializer(settings.session_secret, salt="cor1x-user-session").dumps({"uid": body["userId"], "sv": 0})
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, legacy)
    assert (await client.get("/me")).status_code == 401