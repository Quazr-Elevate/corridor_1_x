"""E2E-ONB — a company getting onto the corridor.

Every test here walks the same path a real browser walks: sign up with a
work email, fill the Passport, attach KYB documents, send for review, and
let Corridor ops decide. Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from conftest import sent_emails
from flows import (
    PDF_BYTES,
    admin_reject,
    admin_verify,
    email_for,
    fill_passport,
    list_lot,
    sign_up,
    submit,
)


# ── The happy path ───────────────────────────────────────────────────


async def test_e2e_onb_100_signup_to_verified(make_client, admin_client, counter):
    """E2E-ONB-100: signup → Passport → KYB → submit → approved → in market.

    The one journey that has to work: a new company ends up verified, with
    a listing a stranger can see.
    """
    t = await sign_up(make_client, counter, prefix="onb100")

    # Straight after signup: a draft business, nothing submitted, work to do.
    me = (await t.client.get("/me")).json()
    assert me["status"] == "draft"
    assert me["verification"]["submittedAt"] is None
    assert me["verification"]["missing"], "a fresh business must list what it needs"
    assert len(me["verification"]["missingLabels"]) == len(me["verification"]["missing"])
    assert me["email"] == t.email

    # A draft business cannot be submitted while fields are missing.
    early = await t.client.post("/me/submit-verification")
    assert early.status_code == 400 and "Missing" in early.json()["detail"]

    await fill_passport(t)
    me = (await t.client.get("/me")).json()
    assert me["verification"]["missing"] == [], me["verification"]["missing"]
    assert me["status"] == "draft", "filling fields never changes status on its own"

    state = await submit(t)
    assert state["status"] == "pending_verification" and state["submittedAt"]

    # The business shows up in the ops review queue.
    queue = (await admin_client.get("/admin/verify/queue")).json()
    assert t.user_id in [row["userId"] for row in queue]

    await admin_verify(admin_client, t)
    me = (await t.client.get("/me")).json()
    assert me["status"] == "verified" and me["verification"]["verifiedAt"]
    assert me["verification"]["rejectedItems"] == []

    # The trader is told by email.
    assert [m for m in sent_emails(t.email) if "verified" in m.subject]

    # A verified business can publish, and the market shows the listing.
    lot = await list_lot(t)
    public = (await make_client().get("/public/products")).json()
    assert public["total"] == 1 and public["items"][0]["id"] == lot["id"]


async def test_e2e_onb_110_resubmitting_a_verified_business_is_refused(make_client, admin_client, counter):
    """E2E-ONB-110: once verified, "Send for verification" is a dead button."""
    t = await sign_up(make_client, counter, prefix="onb110")
    await fill_passport(t)
    await submit(t)
    await admin_verify(admin_client, t)

    r = await t.client.post("/me/submit-verification")
    assert r.status_code == 400 and "already verified" in r.json()["detail"]


async def test_e2e_onb_120_submitting_twice_is_harmless(make_client, counter):
    """E2E-ONB-120: a double-click on "Send for verification" is idempotent."""
    t = await sign_up(make_client, counter, prefix="onb120")
    await fill_passport(t)
    first = await submit(t)
    second = await submit(t)
    assert first["status"] == second["status"] == "pending_verification"
    assert first["submittedAt"] == second["submittedAt"], "the clock must not restart"


# ── Rejection and the way back ───────────────────────────────────────


async def test_e2e_onb_200_rejected_then_fixed_then_verified(make_client, admin_client, counter):
    """E2E-ONB-200: ops rejects named items, the trader fixes them, resubmits,
    and gets through — the full round trip."""
    t = await sign_up(make_client, counter, prefix="onb200")
    await fill_passport(t)
    await submit(t)

    entries = (await t.client.get("/me/verification-docs")).json()
    gstin = [e for e in entries if e["documentTypeCode"] == "gstin"][0]
    await admin_reject(
        admin_client, t, reason="The GSTIN certificate is unreadable.", items=["kyb:gstin", "addressLine"]
    )

    me = (await t.client.get("/me")).json()
    assert me["status"] == "rejected"
    assert me["verification"]["rejectedReason"] == "The GSTIN certificate is unreadable."
    assert set(me["verification"]["rejectedItems"]) == {"kyb:gstin", "addressLine"}
    assert len(me["verification"]["rejectedItemLabels"]) == 2
    assert [m for m in sent_emails(t.email) if "needs changes" in m.subject]

    # The flagged document is back in the trader's court, so the profile
    # reads as incomplete again and ops can't just approve it.
    assert "kyb:gstin" in me["verification"]["missing"]
    blocked = await admin_client.post(f"/admin/users/{t.user_id}/verify")
    assert blocked.status_code == 400 and "incomplete" in blocked.json()["detail"]

    # Fix the flagged items: a new address line and a fresh file on the entry.
    r = await t.client.put(
        "/me/business-profile",
        json={
            "legalName": f"Acme Agro {t.n} Pvt Ltd",
            "country": "IN",
            "addressLine": "12 New Market Road",
            "city": "Karnal",
        },
    )
    assert r.status_code == 200, r.text
    r = await t.client.patch(
        f"/me/verification-docs/{gstin['id']}", files={"file": ("gstin.pdf", PDF_BYTES, "application/pdf")}
    )
    assert r.status_code == 200, r.text

    state = await submit(t)
    assert state["status"] == "pending_verification"
    assert state["rejectedItems"] == [], "resubmitting clears the old flags"
    assert state["rejectedReason"] is None

    await admin_verify(admin_client, t)
    assert (await t.client.get("/me")).json()["status"] == "verified"


async def test_e2e_onb_210_rejection_needs_a_reason_and_known_items(make_client, admin_client, counter):
    """E2E-ONB-210: ops can't reject blindly — a reason is required and an
    unknown item key is refused rather than silently dropped."""
    t = await sign_up(make_client, counter, prefix="onb210")
    await fill_passport(t)
    await submit(t)

    blank = await admin_client.post(f"/admin/users/{t.user_id}/reject", json={"reason": "   "})
    assert blank.status_code == 422

    unknown = await admin_client.post(
        f"/admin/users/{t.user_id}/reject", json={"reason": "No good", "failedItems": ["not_a_field"]}
    )
    assert unknown.status_code == 400

    assert (await t.client.get("/me")).json()["status"] == "pending_verification"


async def test_e2e_onb_220_revoking_a_verified_business_pulls_its_listings(make_client, admin_client, counter):
    """E2E-ONB-220: ops revokes verification — the company's lots leave the
    market at once and come back when it is approved again."""
    t = await sign_up(make_client, counter, prefix="onb220")
    await fill_passport(t)
    await submit(t)
    await admin_verify(admin_client, t)
    lot = await list_lot(t)

    anon = make_client()
    assert (await anon.get("/public/products")).json()["total"] == 1

    await admin_reject(admin_client, t, reason="Licence expired.", items=["legalName"])
    assert (await t.client.get("/me")).json()["status"] == "rejected"
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{lot['id']}")).status_code == 404

    # Ops can approve straight from rejected — no resubmission needed.
    await admin_verify(admin_client, t)
    assert (await anon.get("/public/products")).json()["total"] == 1


# ── Signup guards ────────────────────────────────────────────────────


async def test_e2e_onb_300_signup_rejects_unusable_emails(make_client, counter):
    """E2E-ONB-300: free-mail and disposable addresses never get a code."""
    c = make_client()
    for address in ("someone@gmail.com", "someone@mailinator.com", "not-an-email"):
        r = await c.post("/auth/signup/code", json={"email": address})
        assert r.status_code in (400, 422), f"{address} → {r.status_code}"
        assert sent_emails(address) == []


async def test_e2e_onb_310_signing_up_an_existing_email_sends_you_to_login(make_client, counter):
    """E2E-ONB-310: a company that already has an account is told to sign in,
    not quietly given a second one."""
    t = await sign_up(make_client, counter, prefix="onb310")

    c = make_client()
    r = await c.post("/auth/signup/code", json={"email": t.email})
    # Either the code request or the completion must stop it — never a
    # second account for the same email.
    if r.status_code == 200:
        r = await c.post("/auth/signup/verify", json={"email": t.email, "code": "000000"})
        assert r.status_code == 400
    else:
        assert r.status_code == 409


async def test_e2e_onb_320_wrong_code_five_times_kills_the_code(make_client):
    """E2E-ONB-320: brute-forcing the 6-digit code gets you nowhere."""
    c = make_client()
    email = email_for("onb320")
    assert (await c.post("/auth/signup/code", json={"email": email})).status_code == 200

    for _ in range(5):
        r = await c.post("/auth/signup/verify", json={"email": email, "code": "000000"})
        assert r.status_code == 400, r.text

    # Even the right code is dead now.
    from conftest import code_from_email

    r = await c.post("/auth/signup/verify", json={"email": email, "code": code_from_email(email)})
    assert r.status_code == 400
