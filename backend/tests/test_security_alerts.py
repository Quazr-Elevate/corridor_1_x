"""CX-034 security emails and CX-070 two-factor columns."""
from __future__ import annotations

import sqlite3

import pytest
from conftest import sent_emails, signup_and_login
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from test_migration_0020 import _alembic, _build_0019

from app.core import crypto
from app.core.db import SessionLocal
from app.models.auth_session import AuthEvent
from app.models.user import User
from app.modules.auth.sessions import device_key, device_label

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CHROME_WIN_NEXT = CHROME_WIN.replace("131.0.0.0", "132.0.6834.83")
SAFARI_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
PASSWORD = "Sup3r-secret!"
NEW_PASSWORD = "Another-Strong-Pass-42"


def _subjects(to: str) -> list[str]:
    return [m.subject for m in sent_emails(to)]


async def _login(c, email: str, ua: str, password: str = PASSWORD):
    return await c.post("/auth/login", json={"email": email, "password": password}, headers={"User-Agent": ua})


def test_device_key_and_label():
    assert device_key(CHROME_WIN) == device_key(CHROME_WIN_NEXT) != device_key(SAFARI_IPHONE)
    assert device_label(CHROME_WIN) == "Chrome on Windows"
    assert device_label(SAFARI_IPHONE) == "Safari on iPhone"
    assert device_label(None) == "An unrecognised browser"


async def test_new_device_sign_in_emails_the_user_once(client, make_client):
    email = "alert1@kaverifoods.in"
    client.headers["User-Agent"] = CHROME_WIN
    await signup_and_login(client, email)

    # Same browser, and the same browser after an update: no alert.
    assert (await _login(make_client(), email, CHROME_WIN)).status_code == 200
    assert (await _login(make_client(), email, CHROME_WIN_NEXT)).status_code == 200
    assert "New sign-in to your Cor1x account" not in _subjects(email)

    # A phone it has never seen: one alert, naming the browser but no IP.
    assert (await _login(make_client(), email, SAFARI_IPHONE)).status_code == 200
    alerts = [m for m in sent_emails(email) if m.subject == "New sign-in to your Cor1x account"]
    assert len(alerts) == 1
    assert "Safari on iPhone" in alerts[0].text and "/forgot-password" in alerts[0].text

    # The phone is now known.
    assert (await _login(make_client(), email, SAFARI_IPHONE)).status_code == 200
    assert _subjects(email).count("New sign-in to your Cor1x account") == 1
    async with SessionLocal() as db:
        flagged = [e for e in await db.scalars(select(AuthEvent).where(AuthEvent.event == "login_succeeded")) if e.details]
    assert [e.details for e in flagged] == [{"new_device": True}]


async def test_wrong_password_from_a_new_device_sends_nothing(client, make_client):
    email = "alert2@kaverifoods.in"
    await signup_and_login(client, email)
    assert (await _login(make_client(), email, SAFARI_IPHONE, "wrong-password")).status_code == 401
    assert "New sign-in to your Cor1x account" not in _subjects(email)


async def test_password_change_emails_the_user(client):
    email = "alert3@kaverifoods.in"
    await signup_and_login(client, email)
    r = await client.post("/auth/change-password", json={"currentPassword": "nope-nope-nope", "newPassword": NEW_PASSWORD})
    assert r.status_code == 401
    assert "Your Cor1x password was changed" not in _subjects(email)

    r = await client.post("/auth/change-password", json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD})
    assert r.status_code == 200, r.text
    mail = [m for m in sent_emails(email) if m.subject == "Your Cor1x password was changed"]
    assert len(mail) == 1 and "/forgot-password" in mail[0].text
    assert NEW_PASSWORD not in mail[0].text and NEW_PASSWORD not in mail[0].html


async def test_password_reset_emails_the_user(client, make_client):
    email = "alert4@kaverifoods.in"
    await signup_and_login(client, email)
    anon = make_client()
    assert (await anon.post("/auth/password/forgot", json={"email": email})).status_code == 200
    code = [m for m in sent_emails(email) if "password reset code" in m.subject][-1].text
    import re

    r = await anon.post(
        "/auth/password/reset", json={"email": email, "code": re.search(r"\b(\d{6})\b", code).group(1), "newPassword": NEW_PASSWORD}
    )
    assert r.status_code == 200, r.text
    assert _subjects(email).count("Your Cor1x password was changed") == 1


async def test_totp_columns_start_empty_and_stay_paired(client):
    await signup_and_login(client, "totp@kaverifoods.in")
    async with SessionLocal() as db:
        user = await db.scalar(select(User))
        assert (user.totp_secret_encrypted, user.totp_secret_key_version, user.backup_codes) == (None, None, None)
        # A secret without its key version could never be decrypted: the database refuses it.
        with pytest.raises(IntegrityError):
            await db.execute(update(User).values(totp_secret_encrypted="x"))
        await db.rollback()
        secret, version = crypto.encrypt("JBSWY3DPEHPK3PXP")
        await db.execute(update(User).values(totp_secret_encrypted=secret, totp_secret_key_version=version))
        await db.commit()
        stored = await db.scalar(select(User))
        await db.refresh(stored)
        assert crypto.decrypt(stored.totp_secret_encrypted, stored.totp_secret_key_version) == "JBSWY3DPEHPK3PXP"


def test_0025_adds_and_removes_the_columns(tmp_path):
    db = tmp_path / "v24.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0024_identity_access").returncode == 0
    proc = _alembic(db, "upgrade", "0025_totp_columns")
    assert proc.returncode == 0, proc.stderr

    wanted = {"totp_secret_encrypted", "totp_secret_key_version", "backup_codes"}
    con = sqlite3.connect(db)
    for table in ("users", "admin_users"):
        assert wanted <= {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    # Existing accounts are untouched and still valid.
    assert con.execute("SELECT count(*) FROM users WHERE totp_secret_encrypted IS NOT NULL").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE users SET totp_secret_encrypted = 'x'")
    con.close()

    proc = _alembic(db, "downgrade", "0024_identity_access")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    for table in ("users", "admin_users"):
        assert not wanted & {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    con.close()
