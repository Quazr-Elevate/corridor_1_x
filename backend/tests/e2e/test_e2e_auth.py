"""E2E-AUTH — signing in, staying in, getting out, getting locked out.

These follow one account across several browsers (each ``make_client()`` is
a separate cookie jar), which is the only honest way to test "one device
per account". Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from conftest import sent_emails
from flows import PASSWORD, login, reset_password, sign_up


# ── Sessions ─────────────────────────────────────────────────────────


async def test_e2e_auth_100_signing_in_elsewhere_signs_you_out_here(make_client, counter):
    """E2E-AUTH-100: one device per account — the laptop drops when the same
    account signs in on the phone."""
    laptop = await sign_up(make_client, counter, prefix="auth100")
    assert (await laptop.client.get("/me")).status_code == 200

    phone = make_client()
    assert (await login(phone, laptop.email, PASSWORD)).status_code == 200
    assert (await phone.get("/me")).status_code == 200
    assert (await laptop.client.get("/me")).status_code == 401, "the old device must be signed out"

    # The security page tells the user what happened.
    overview = (await phone.get("/auth/security")).json()
    assert overview["device"] is not None
    assert "session_replaced" in [e["event"] for e in overview["recent"]]


async def test_e2e_auth_110_logout_and_logout_all(make_client, counter):
    """E2E-AUTH-110: signing out ends the session server-side, and the cookie
    is useless afterwards."""
    t = await sign_up(make_client, counter, prefix="auth110")
    assert (await t.client.post("/auth/logout")).status_code == 200
    assert (await t.client.get("/me")).status_code == 401

    phone = make_client()
    assert (await login(phone, t.email, PASSWORD)).status_code == 200
    assert (await phone.post("/auth/logout-all")).status_code == 200
    assert (await phone.get("/me")).status_code == 401

    # Logging out twice is harmless.
    assert (await phone.post("/auth/logout")).status_code == 200


async def test_e2e_auth_120_changing_password_keeps_this_browser(make_client, counter):
    """E2E-AUTH-120: a password change keeps the browser that made it and
    invalidates the old password."""
    t = await sign_up(make_client, counter, prefix="auth120")
    r = await t.client.post(
        "/auth/change-password", json={"currentPassword": PASSWORD, "newPassword": "Even-better-99!"}
    )
    assert r.status_code == 200, r.text
    assert (await t.client.get("/me")).status_code == 200, "this browser stays signed in"

    other = make_client()
    assert (await login(other, t.email, PASSWORD)).status_code == 401
    assert (await login(other, t.email, "Even-better-99!")).status_code == 200

    # The wrong current password is refused.
    bad = await other.post("/auth/change-password", json={"currentPassword": "nope", "newPassword": "Another-one-99!"})
    assert bad.status_code in (400, 401)


async def test_e2e_auth_130_password_reset_round_trip(make_client, counter):
    """E2E-AUTH-130: forgot password → emailed code → new password, and every
    session is signed out."""
    t = await sign_up(make_client, counter, prefix="auth130")
    anon = make_client()
    await reset_password(anon, t.email, "Brand-new-pass-7!")

    assert (await t.client.get("/me")).status_code == 401, "the reset signs every device out"
    assert (await login(anon, t.email, PASSWORD)).status_code == 401
    assert (await login(anon, t.email, "Brand-new-pass-7!")).status_code == 200


async def test_e2e_auth_140_reset_for_an_unknown_email_gives_nothing_away(make_client):
    """E2E-AUTH-140: the forgot-password answer never reveals who has an
    account."""
    unknown = "ghost@notregistered.in"
    r = await make_client().post("/auth/password/forgot", json={"email": unknown})
    assert r.status_code == 200 and "If an account exists" in r.json()["message"]
    assert sent_emails(unknown) == []


# ── Lockout ──────────────────────────────────────────────────────────


async def test_e2e_auth_200_five_wrong_passwords_lock_the_account(make_client, counter):
    """E2E-AUTH-200: five wrong passwords lock the account for a while — and
    the *right* password is refused too until it clears."""
    t = await sign_up(make_client, counter, prefix="auth200")
    anon = make_client()

    for attempt in range(4):
        r = await login(anon, t.email, "wrong-password")
        assert r.status_code == 401, f"attempt {attempt + 1} → {r.status_code}"

    # The fifth failure is the one that locks it.
    fifth = await login(anon, t.email, "wrong-password")
    assert fifth.status_code == 423, fifth.text

    locked = await login(anon, t.email, PASSWORD)
    assert locked.status_code == 423, locked.text
    assert "minute" in locked.json()["detail"].lower() or "locked" in locked.json()["detail"].lower()

    # The owner can see it on their security page once they get back in.
    assert [e for e in (await t.client.get("/auth/security")).json()["recent"] if e["event"] == "locked"]


async def test_e2e_auth_210_support_can_unlock_a_trader(make_client, admin_client, counter):
    """E2E-AUTH-210: a locked-out trader is let back in by Corridor ops."""
    t = await sign_up(make_client, counter, prefix="auth210")
    anon = make_client()
    for _ in range(5):
        await login(anon, t.email, "wrong-password")
    assert (await login(anon, t.email, PASSWORD)).status_code == 423

    r = await admin_client.post(f"/admin/users/{t.user_id}/unlock")
    assert r.status_code == 200, r.text
    assert (await login(anon, t.email, PASSWORD)).status_code == 200


async def test_e2e_auth_220_ops_can_sign_a_trader_out(make_client, admin_client, counter):
    """E2E-AUTH-220: ops ends a trader's session; the trader's next call 401s."""
    t = await sign_up(make_client, counter, prefix="auth220")
    assert (await t.client.get("/me")).status_code == 200

    r = await admin_client.post(f"/admin/users/{t.user_id}/sign-out")
    assert r.status_code == 200, r.text
    assert (await t.client.get("/me")).status_code == 401


# ── Account closure ──────────────────────────────────────────────────


async def test_e2e_auth_300_closing_an_account_pulls_its_listings(make_client, admin_client, counter):
    """E2E-AUTH-300: right to erasure — the account is closed, the session is
    dead, the email can't sign in, and the company's lots leave the market."""
    from flows import list_lot, verified_trader

    t = await verified_trader(make_client, admin_client, counter, prefix="auth300")
    await list_lot(t)
    anon = make_client()
    assert (await anon.get("/public/products")).json()["total"] == 1

    r = await t.client.delete("/me")
    assert r.status_code == 204, r.text
    assert (await t.client.get("/me")).status_code == 401
    assert (await login(anon, t.email, PASSWORD)).status_code in (401, 423)
    assert (await anon.get("/public/products")).json()["total"] == 0


# ── Guards ───────────────────────────────────────────────────────────


async def test_e2e_auth_400_protected_routes_need_a_session(make_client):
    """E2E-AUTH-400: every private route answers 401 to an anonymous caller
    (the frontend's middleware redirect depends on this)."""
    anon = make_client()
    for method, path in (
        ("get", "/me"),
        ("get", "/onboarding/status"),
        ("get", "/products"),
        ("get", "/me/verification-docs"),
        ("get", "/kyb/document-types"),
        ("get", "/auth/security"),
        ("post", "/me/submit-verification"),
        ("post", "/auth/logout-all"),
    ):
        r = await getattr(anon, method)(path)
        assert r.status_code == 401, f"{method.upper()} {path} → {r.status_code}"

    # /auth/session is the exception: it answers for anonymous callers too.
    r = await anon.get("/auth/session")
    assert r.status_code == 200 and r.json()["userId"] is None


async def test_e2e_auth_410_a_tampered_session_cookie_is_rejected(make_client, counter):
    """E2E-AUTH-410: the cookie is an opaque token — editing it doesn't work."""
    t = await sign_up(make_client, counter, prefix="auth410")
    jar = make_client()
    jar.cookies.set("cor1x_session", "a" * 43, domain="testserver")
    assert (await jar.get("/me")).status_code == 401
