"""Phase A — server-side sessions (one device), timeouts, lockout, password
reset, security overview, headers, actor in logs."""
from __future__ import annotations

import re
from datetime import timedelta

from conftest import sent_emails, signup_and_login
from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.core.security import SESSION_COOKIE, hash_token
from app.core.time import utcnow
from app.models.auth_session import AuthEvent, UserSession
from app.models.user import User
from app.ratelimit import get_limiter

PW = "Sup3r-secret!"


async def _login(c, email, password=PW):
    return await c.post("/auth/login", json={"email": email, "password": password})


async def _events(user_email: str) -> list[str]:
    async with SessionLocal() as db:
        uid = await db.scalar(select(User.id).where(User.email == user_email))
        return list(await db.scalars(
            select(AuthEvent.event).where(AuthEvent.subject_id == uid).order_by(AuthEvent.created_at)
        ))


# ── Sessions ─────────────────────────────────────────────────────────


async def test_session_cookie_is_opaque_and_only_hash_stored(client):
    await signup_and_login(client, "opaque@kaverifoods.in")
    token = client.cookies.get(SESSION_COOKIE)
    assert "." not in token  # not a signed JSON payload
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(UserSession)))
    assert len(rows) == 1 and rows[0].token_hash == hash_token(token) and token not in rows[0].token_hash


async def test_second_device_signs_out_the_first(client, make_client):
    email = "onedev@kaverifoods.in"
    await signup_and_login(client, email)
    other = make_client()
    assert (await _login(other, email)).status_code == 200
    assert (await other.get("/me")).status_code == 200
    assert (await client.get("/me")).status_code == 401
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(UserSession).order_by(UserSession.created_at)))
    assert [r.revoked_reason for r in rows] == ["replaced", None]
    assert "session_replaced" in await _events(email)


async def test_idle_timeout(client):
    await signup_and_login(client, "idle@kaverifoods.in")
    async with SessionLocal() as db:
        await db.execute(update(UserSession).values(last_seen_at=utcnow() - timedelta(hours=12, minutes=1)))
        await db.commit()
    assert (await client.get("/me")).status_code == 401


async def test_absolute_timeout(client):
    await signup_and_login(client, "abs@kaverifoods.in")
    async with SessionLocal() as db:
        await db.execute(update(UserSession).values(expires_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert (await client.get("/me")).status_code == 401


async def test_logout_revokes_server_side(client, make_client):
    await signup_and_login(client, "out@kaverifoods.in")
    token = client.cookies.get(SESSION_COOKIE)
    assert (await client.post("/auth/logout")).status_code == 200
    replay = make_client()
    replay.cookies.set(SESSION_COOKIE, token)
    assert (await replay.get("/me")).status_code == 401


async def test_cookie_max_age_is_seven_days(make_client):
    c = make_client()
    await signup_and_login(c, "maxage@kaverifoods.in")
    r = await _login(c, "maxage@kaverifoods.in")
    cookie = r.headers["set-cookie"]
    assert "Max-Age=604800" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie


async def test_security_overview(client):
    email = "secview@kaverifoods.in"
    await signup_and_login(client, email, password=PW)
    await _login(client, email, "wrong-password")
    await _login(client, email)
    r = await client.get("/auth/security")
    assert r.status_code == 200
    body = r.json()
    assert body["device"]["current"] is True and body["idleTimeoutMinutes"] == 720 and body["maxSessionDays"] == 7
    events = [e["event"] for e in body["recent"]]
    assert events[0] == "session_replaced" or events[0] == "login_succeeded"
    assert {"login_succeeded", "login_failed", "session_replaced"} <= set(events)


async def test_account_deletion_revokes_session(client):
    await signup_and_login(client, "gone@kaverifoods.in")
    assert (await client.delete("/me")).status_code == 204
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(UserSession)))
    assert rows and all(r.revoked_at is not None for r in rows)


# ── Lockout ──────────────────────────────────────────────────────────


async def _fail(c, email, n):
    return [(await _login(c, email, "wrong-password")).status_code for _ in range(n)]


async def _expire_lock(email):
    """Jump past the lock (and the per-email login rate-limit window, which
    real time would also have cleared)."""
    await get_limiter().reset()
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(locked_until=utcnow() - timedelta(seconds=1)))
        await db.commit()


async def test_lockout_escalates_to_support(client, make_client):
    email = "lock@kaverifoods.in"
    await signup_and_login(client, email)
    c = make_client()
    assert await _fail(c, email, 5) == [401, 401, 401, 401, 423]
    r = await _login(c, email)  # right password, still locked
    assert r.status_code == 423 and "15 minutes" in r.json()["detail"]

    await _expire_lock(email)
    assert await _fail(c, email, 5) == [401, 401, 401, 401, 423]
    async with SessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == email))
        assert u.lockout_count == 2
        assert timedelta(minutes=29) < u.locked_until - utcnow() <= timedelta(minutes=30)

    await _expire_lock(email)
    codes = await _fail(c, email, 5)
    assert codes[-1] == 423
    r = await _login(c, email)
    assert r.status_code == 423 and "contact support" in r.json()["detail"]
    assert "enquiry@corridor1x.com" in r.json()["detail"]
    assert {"locked", "locked_support"} <= set(await _events(email))


async def test_success_resets_counters(client, make_client):
    email = "reset-count@kaverifoods.in"
    await signup_and_login(client, email)
    c = make_client()
    assert await _fail(c, email, 4) == [401] * 4
    assert (await _login(c, email)).status_code == 200
    assert await _fail(c, email, 4) == [401] * 4  # counter started over


async def test_admin_unlocks_support_lock(client, make_client, admin_client):
    email = "unlockme@kaverifoods.in"
    body = await signup_and_login(client, email)
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(lockout_count=3, locked_until=None))
        await db.commit()
    c = make_client()
    assert (await _login(c, email)).status_code == 423
    detail = (await admin_client.get(f"/admin/users/{body['userId']}")).json()
    assert detail["security"]["lockState"] == "support"
    assert (await admin_client.post(f"/admin/users/{body['userId']}/unlock")).status_code == 200
    assert (await _login(c, email)).status_code == 200


async def test_admin_signs_out_trader(client, admin_client):
    body = await signup_and_login(client, "kick@kaverifoods.in")
    assert (await admin_client.post(f"/admin/users/{body['userId']}/sign-out")).status_code == 200
    assert (await client.get("/me")).status_code == 401


# ── Password reset ───────────────────────────────────────────────────


def _reset_code(email: str) -> str:
    msg = [m for m in sent_emails(email) if "password reset code" in m.subject][-1]
    return re.search(r"\b(\d{6})\b", msg.text).group(1)


async def test_password_reset_flow(client, make_client):
    email = "forgot@kaverifoods.in"
    await signup_and_login(client, email)
    anon = make_client()
    r = await anon.post("/auth/password/forgot", json={"email": email})
    assert r.status_code == 200 and r.json().get("devCode") is None
    code = _reset_code(email)
    bad = await anon.post("/auth/password/reset", json={"email": email, "code": "000000", "newPassword": "Fresh-pass-99"})
    assert bad.status_code == 400
    ok = await anon.post("/auth/password/reset", json={"email": email, "code": code, "newPassword": "Fresh-pass-99"})
    assert ok.status_code == 200, ok.text
    assert (await client.get("/me")).status_code == 401  # every session signed out
    assert (await _login(anon, email)).status_code == 401
    assert (await _login(anon, email, "Fresh-pass-99")).status_code == 200
    # Single use.
    again = await anon.post("/auth/password/reset", json={"email": email, "code": code, "newPassword": "Other-pass-99"})
    assert again.status_code == 400


async def test_password_reset_unknown_email_looks_the_same(make_client):
    r = await make_client().post("/auth/password/forgot", json={"email": "nobody@kaverifoods.in"})
    assert r.status_code == 200 and "If an account exists" in r.json()["message"]
    assert sent_emails("nobody@kaverifoods.in") == []


async def test_password_reset_keeps_support_lock(client, make_client):
    email = "stilllocked@kaverifoods.in"
    await signup_and_login(client, email)
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(lockout_count=3))
        await db.commit()
    anon = make_client()
    await anon.post("/auth/password/forgot", json={"email": email})
    r = await anon.post(
        "/auth/password/reset", json={"email": email, "code": _reset_code(email), "newPassword": "Fresh-pass-99"}
    )
    assert r.status_code == 200
    assert (await _login(anon, email, "Fresh-pass-99")).status_code == 423


# ── Headers / logs ───────────────────────────────────────────────────


async def test_security_headers_and_no_store(client):
    await signup_and_login(client, "hdr@kaverifoods.in")
    r = await client.get("/me")
    h = r.headers
    assert h["cache-control"] == "no-store"
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'self' http://localhost:3000" in h["content-security-policy"]
    assert "strict-transport-security" not in h  # COOKIE_SECURE=false in tests


async def test_access_log_carries_actor(client, caplog):
    import logging

    body = await signup_and_login(client, "actor@kaverifoods.in")
    with caplog.at_level(logging.INFO, logger="app.access"):
        await client.get("/me")
    actors = [getattr(r, "actor", None) for r in caplog.records if r.name == "app.access"]
    assert f"user:{body['userId']}" in actors


async def test_cors_localhost_regex_off_outside_debug(make_client):
    r = await make_client().options(
        "/auth/login", headers={"Origin": "http://localhost:5555", "Access-Control-Request-Method": "POST"}
    )
    assert r.headers.get("access-control-allow-origin") != "http://localhost:5555"


def test_insecure_defaults_refused():
    import pytest

    from app.core.config import Settings
    from app.main import create_app

    s = Settings(debug=False, session_secret="dev-only-session-secret-change-me")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        create_app(s)


def test_ip_helpers():
    from app.core.security import ip_allowed, ip_prefix

    assert ip_prefix("203.0.113.77") == "203.0.113.0/24"
    assert ip_prefix("2001:db8:abcd:12::1") == "2001:db8:abcd::/48"
    assert ip_prefix("garbage") is None
    assert ip_allowed("1.2.3.4", [])
    assert ip_allowed("10.1.2.3", ["10.0.0.0/8"]) and not ip_allowed("11.1.2.3", ["10.0.0.0/8", "bad"])

