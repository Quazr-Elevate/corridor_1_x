from __future__ import annotations

from datetime import timedelta

from conftest import code_from_email, sent_emails, signup_and_login
from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.core.security import SESSION_COOKIE
from app.models.business import Business, BusinessStatus
from app.models.email_code import EmailCode
from app.models.user import User


async def _code(client, email: str) -> str:
    r = await client.post("/auth/signup/code", json={"email": email})
    assert r.status_code == 200, r.text
    return code_from_email(email)


def _complete(email: str, **over) -> dict:
    body = {
        "email": email,
        "fullName": "Asha Rao",
        "companyName": f"{email.split('@')[0]} Exports",
        "position": "Director",
        "password": "Sup3r-secret!",
        "acceptTerms": True,
    }
    body.update(over)
    return body


async def _age_codes(email: str, **delta) -> None:
    """Move every code for ``email`` into the past (created/expiry/verified)."""
    async with SessionLocal() as db:
        for row in await db.scalars(select(EmailCode).where(EmailCode.email == email)):
            row.created_at = row.created_at - timedelta(**delta)
            row.expires_at = row.expires_at - timedelta(**delta)
            if row.verified_at is not None:
                row.verified_at = row.verified_at - timedelta(**delta)
        await db.commit()


async def test_signup_code_verify_complete_logs_in(client):
    email = "asha@kaverifoods.in"
    r = await client.post("/auth/signup/code", json={"email": "Asha@KaveriFoods.in"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email and body["resendInSec"] == 60 and body["expiresInSec"] == 600
    assert body["devCode"] is None  # DEBUG=false → never leaked
    [mail] = sent_emails(email)
    assert "verification code" in mail.subject
    code = code_from_email(email)

    # Only the hash is stored.
    async with SessionLocal() as db:
        row = await db.scalar(select(EmailCode).where(EmailCode.email == email))
        assert row.code_hash != code and len(row.code_hash) == 64

    assert (await client.post("/auth/signup/verify", json={"email": email, "code": code})).status_code == 200
    r = await client.post("/auth/signup/complete", json=_complete(email))
    assert r.status_code == 201, r.text
    login = r.json()
    assert set(login) == {"userId", "businessId", "role", "email", "businessName"}
    assert login["role"] == "owner" and login["businessName"] == "asha Exports"
    assert client.cookies.get(SESSION_COOKIE)

    me = (await client.get("/me")).json()
    assert me["userId"] == login["userId"] and me["businessId"] == login["businessId"]
    assert me["role"] == "owner" and me["status"] == "draft"
    assert me["emailVerifiedAt"]
    assert me["primary"] == {"fullName": "Asha Rao", "phone": None, "position": "Director"}
    assert me["business"]["country"] == "IN"
    for gone in ("mustChangePassword", "completion", "bank"):
        assert gone not in me

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        assert user.consent_at and user.consent_version and user.email_verified_at
        assert user.business.verification_status == BusinessStatus.draft
        row = await db.scalar(select(EmailCode).where(EmailCode.email == email))
        assert row.verified_at and row.consumed_at

    # Login works with email + password only.
    client.cookies.clear()
    r = await client.post("/auth/login", json={"email": email, "password": "Sup3r-secret!"})
    assert r.status_code == 200 and r.json()["businessId"] == login["businessId"]


async def test_wrong_code_five_times_locks(client):
    email = "lock@kaverifoods.in"
    code = await _code(client, email)
    wrong = "000000" if code != "000000" else "111111"
    details = []
    for _ in range(5):
        r = await client.post("/auth/signup/verify", json={"email": email, "code": wrong})
        assert r.status_code == 400
        details.append(r.json()["detail"])
    assert "4 attempts left" in details[0]
    assert "Too many wrong attempts" in details[-1]
    # Even the right code is now dead.
    r = await client.post("/auth/signup/verify", json={"email": email, "code": code})
    assert r.status_code == 400 and "Too many wrong attempts" in r.json()["detail"]
    assert (await client.post("/auth/signup/complete", json=_complete(email))).status_code == 400


async def test_expired_code(client):
    email = "late@kaverifoods.in"
    code = await _code(client, email)
    await _age_codes(email, minutes=11)
    r = await client.post("/auth/signup/verify", json={"email": email, "code": code})
    assert r.status_code == 400 and "expired" in r.json()["detail"]


async def test_complete_requires_verified_code_within_30_min(client):
    email = "skip@kaverifoods.in"
    r = await client.post("/auth/signup/complete", json=_complete(email))
    assert r.status_code == 400 and "Verify your email" in r.json()["detail"]
    code = await _code(client, email)
    r = await client.post("/auth/signup/complete", json=_complete(email))
    assert r.status_code == 400 and "Verify your email" in r.json()["detail"]
    assert (await client.post("/auth/signup/verify", json={"email": email, "code": code})).status_code == 200
    await _age_codes(email, minutes=31)
    r = await client.post("/auth/signup/complete", json=_complete(email))
    assert r.status_code == 400 and "expired" in r.json()["detail"]


async def test_complete_validation(client):
    email = "val@kaverifoods.in"
    code = await _code(client, email)
    await client.post("/auth/signup/verify", json={"email": email, "code": code})
    assert (await client.post("/auth/signup/complete", json=_complete(email, acceptTerms=False))).status_code == 422
    assert (await client.post("/auth/signup/complete", json=_complete(email, password="short"))).status_code == 422
    assert (await client.post("/auth/signup/complete", json=_complete(email, fullName="R2D2"))).status_code == 422
    assert (await client.post("/auth/signup/complete", json=_complete(email))).status_code == 201


async def test_double_complete_rejected(client, make_client):
    email = "twice@kaverifoods.in"
    await signup_and_login(client, email)
    other = make_client()
    r = await other.post("/auth/signup/complete", json=_complete(email))
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    async with SessionLocal() as db:
        assert len(list(await db.scalars(select(User).where(User.email == email)))) == 1


async def test_resend_cooldown_and_hourly_cap(client):
    email = "resend@kaverifoods.in"
    first = await _code(client, email)
    r = await client.post("/auth/signup/code", json={"email": email})
    assert r.status_code == 429
    assert "wait" in r.json()["detail"] and int(r.headers["Retry-After"]) <= 60

    # After the cooldown a new code is issued and the old one stops working.
    await _age_codes(email, seconds=61)
    second = await _code(client, email)
    if second != first:
        r = await client.post("/auth/signup/verify", json={"email": email, "code": first})
        assert r.status_code == 400
    assert (await client.post("/auth/signup/verify", json={"email": email, "code": second})).status_code == 200

    # Max 5 codes per hour per email.
    for _ in range(3):
        await _age_codes(email, seconds=61)
        assert (await client.post("/auth/signup/code", json={"email": email})).status_code == 200
    await _age_codes(email, seconds=61)
    r = await client.post("/auth/signup/code", json={"email": email})
    assert r.status_code == 429 and "Too many codes" in r.json()["detail"]


async def test_existing_email_is_409(client, make_client):
    await signup_and_login(client, "dup@kaverifoods.in")
    other = make_client()
    r = await other.post("/auth/signup/code", json={"email": "DUP@kaverifoods.in"})
    assert r.status_code == 409
    assert r.json()["detail"] == "An account with this email already exists. Please log in."


async def test_work_email_required(client):
    r = await client.post("/auth/signup/code", json={"email": "someone@gmail.com"})
    assert r.status_code == 400 and "company email" in r.json()["detail"]
    assert (await client.post("/auth/signup/code", json={"email": "nope"})).status_code == 422


async def test_removed_auth_routes(client):
    assert (await client.post("/auth/signup", json={"email": "x@kaverifoods.in"})).status_code in (404, 405)
    assert (await client.post("/auth/signup/resend", json={"email": "x@kaverifoods.in"})).status_code in (404, 405)
    assert (await client.get("/auth/magic?token=x")).status_code == 404


async def test_change_password_and_revocation(client, make_client):
    email = "rot@kaverifoods.in"
    await signup_and_login(client, email)
    cookie = client.cookies.get(SESSION_COOKIE)

    # Rotation needs the current password.
    r = await client.post("/auth/change-password", json={"currentPassword": "", "newPassword": "N3w-password!"})
    assert r.status_code == 422
    r = await client.post("/auth/change-password", json={"currentPassword": "nope", "newPassword": "N3w-password!"})
    assert r.status_code == 401
    r = await client.post(
        "/auth/change-password", json={"currentPassword": "Sup3r-secret!", "newPassword": "Sup3r-secret!"}
    )
    assert r.status_code == 400
    r = await client.post(
        "/auth/change-password", json={"currentPassword": "Sup3r-secret!", "newPassword": "N3w-password!"}
    )
    assert r.status_code == 200, r.text
    # This browser stays signed in on the same session.
    assert client.cookies.get(SESSION_COOKIE) == cookie
    assert (await client.get("/me")).status_code == 200

    fresh = make_client()
    assert (await fresh.post("/auth/login", json={"email": email, "password": "Sup3r-secret!"})).status_code == 401
    assert (await fresh.post("/auth/login", json={"email": email, "password": "N3w-password!"})).status_code == 200
    # One device: the new sign-in ended the first browser's session.
    assert (await client.get("/me")).status_code == 401
    client.cookies.set(SESSION_COOKIE, fresh.cookies.get(SESSION_COOKIE))

    assert (await client.post("/auth/logout")).status_code == 200
    assert (await client.get("/me")).status_code == 401

    third = make_client()
    await third.post("/auth/login", json={"email": email, "password": "N3w-password!"})
    assert (await third.post("/auth/logout-all")).status_code == 200
    assert (await fresh.get("/me")).status_code == 401


async def test_disabled_account_cannot_log_in(client, make_client):
    email = "off@kaverifoods.in"
    await signup_and_login(client, email)
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(account_status="disabled"))
        await db.commit()
    assert (await client.get("/me")).status_code == 401
    r = await make_client().post("/auth/login", json={"email": email, "password": "Sup3r-secret!"})
    assert r.status_code == 403


async def test_x_user_id_header_is_ignored(client, make_client):
    body = await signup_and_login(client, "victim@kaverifoods.in")
    attacker = make_client()
    r = await attacker.get("/me", headers={"X-User-Id": body["userId"]})
    assert r.status_code == 401
    r = await attacker.post("/products/upload-photo", headers={"X-User-Id": body["userId"]})
    assert r.status_code in (401, 422)


async def test_login_rate_limited(client):
    email = "limit@kaverifoods.in"
    statuses = []
    for _ in range(11):
        r = await client.post("/auth/login", json={"email": email, "password": "x"})
        statuses.append(r.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    assert int(r.headers["Retry-After"]) > 0
    assert "Too many attempts" in r.json()["detail"]


async def test_health_and_request_id(client, monkeypatch):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers.get("x-request-id")

    import app.modules.health.router as health

    async def down() -> bool:
        return False

    monkeypatch.setattr(health, "ping_db", down)
    r = await client.get("/health")
    assert r.status_code == 503


async def test_business_created_per_signup(client, make_client):
    a = await signup_and_login(client, "a@kaverifoods.in")
    b = await signup_and_login(make_client(), "b@othermill.in")
    assert a["businessId"] != b["businessId"]
    async with SessionLocal() as db:
        assert len(list(await db.scalars(select(Business)))) == 2
