"""E2E-ADM — the ops console: who gets in, what they may do, what is logged.

Covers the named-admin lifecycle (bootstrap → create reviewer → temporary
password → first sign-in), role limits, per-document review and the audit
trail. Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, sent_emails
from flows import PDF_BYTES, admin_verify, email_for, fill_passport, sign_up, submit
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.admin_action import AdminAction


async def _actions(action: str | None = None) -> list[AdminAction]:
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AdminAction).order_by(AdminAction.created_at)))
    return [r for r in rows if action is None or r.action == action]


async def _submitted(make_client, counter, *, prefix: str):
    t = await sign_up(make_client, counter, prefix=prefix)
    await fill_passport(t)
    await submit(t)
    return t


# ── Getting into the tower ───────────────────────────────────────────


async def test_e2e_adm_100_admin_signs_in_and_sees_the_console(admin_client):
    """E2E-ADM-100: the bootstrap super admin can open every console view."""
    me = (await admin_client.get("/admin/me")).json()
    assert me["email"] == ADMIN_EMAIL and me["role"] == "super_admin"
    assert "kyb.review" in me["permissions"] and "admins.manage" in me["permissions"]
    assert me["mustChangePassword"] is False

    for path in (
        "/admin/dashboard/stats",
        "/admin/dashboard/timeline",
        "/admin/dashboard/stuck",
        "/admin/verify/queue",
        "/admin/users",
        "/admin/docs/pending",
        "/admin/kyb/document-types",
        "/admin/admins",
    ):
        r = await admin_client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code} {r.text}"


async def test_e2e_adm_110_console_is_closed_to_everyone_else(make_client, counter):
    """E2E-ADM-110: no admin cookie, no console — and a trader's own session
    is not an admin session."""
    anon = make_client()
    for path in ("/admin/me", "/admin/dashboard/stats", "/admin/users", "/admin/verify/queue"):
        assert (await anon.get(path)).status_code == 401, path

    trader = await sign_up(make_client, counter, prefix="adm110")
    assert (await trader.client.get("/admin/users")).status_code == 401

    bad = await anon.post("/admin/login", json={"email": ADMIN_EMAIL, "password": "not-it"})
    assert bad.status_code == 401


async def test_e2e_adm_120_super_admin_onboards_a_reviewer(make_client):
    """E2E-ADM-120: a new reviewer is created with a one-time password, must
    change it on first sign-in, and only then gets to work."""
    from conftest import ADMIN_EMAIL as _  # noqa: F401  (documents the bootstrap source)

    super_admin = make_client()
    assert (await super_admin.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})).status_code == 200

    email = email_for("reviewer", domain="cor1x.test")
    r = await super_admin.post(
        "/admin/admins", json={"email": email, "fullName": "Rhea Nair", "role": "reviewer"}
    )
    assert r.status_code == 201, r.text
    created = r.json()
    temp_password = created["temporaryPassword"]
    assert created["admin"]["role"] == "reviewer" and created["admin"]["mustChangePassword"] is True

    reviewer = make_client()
    r = await reviewer.post("/admin/login", json={"email": email, "password": temp_password})
    assert r.status_code == 200, r.text
    assert r.json()["mustChangePassword"] is True

    # Until the password is changed, real work is blocked.
    blocked = await reviewer.get("/admin/verify/queue")
    assert blocked.status_code == 403, blocked.text

    r = await reviewer.post(
        "/admin/change-password", json={"currentPassword": temp_password, "newPassword": "reviewer-pass-123456"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["mustChangePassword"] is False
    assert (await reviewer.get("/admin/verify/queue")).status_code == 200

    # The one-time password is spent.
    again = make_client()
    assert (await again.post("/admin/login", json={"email": email, "password": temp_password})).status_code == 401


async def test_e2e_adm_130_a_reviewer_cannot_manage_admins_or_the_catalogue(make_client):
    """E2E-ADM-130: roles are real — a reviewer reviews, nothing more."""
    super_admin = make_client()
    await super_admin.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    email = email_for("reviewer2", domain="cor1x.test")
    created = (
        await super_admin.post("/admin/admins", json={"email": email, "fullName": "Dev Patel", "role": "reviewer"})
    ).json()

    reviewer = make_client()
    await reviewer.post("/admin/login", json={"email": email, "password": created["temporaryPassword"]})
    await reviewer.post(
        "/admin/change-password",
        json={"currentPassword": created["temporaryPassword"], "newPassword": "reviewer-pass-123456"},
    )

    # Allowed.
    assert (await reviewer.get("/admin/verify/queue")).status_code == 200
    assert (await reviewer.get("/admin/kyb/document-types")).status_code == 200

    # Denied.
    assert (await reviewer.get("/admin/admins")).status_code == 403
    assert (
        await reviewer.post("/admin/admins", json={"email": "x@cor1x.test", "fullName": "No One", "role": "reviewer"})
    ).status_code == 403
    assert (
        await reviewer.post(
            "/admin/kyb/document-types", json={"country": "IN", "code": "sneaky", "name": "Sneaky", "inputKind": "file"}
        )
    ).status_code == 403


async def test_e2e_adm_140_a_disabled_admin_loses_access(make_client):
    """E2E-ADM-140: disabling an admin account shuts the door immediately."""
    super_admin = make_client()
    await super_admin.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    email = email_for("reviewer3", domain="cor1x.test")
    created = (
        await super_admin.post("/admin/admins", json={"email": email, "fullName": "Ira Shah", "role": "reviewer"})
    ).json()
    admin_id = created["admin"]["id"]

    reviewer = make_client()
    await reviewer.post("/admin/login", json={"email": email, "password": created["temporaryPassword"]})
    await reviewer.post(
        "/admin/change-password",
        json={"currentPassword": created["temporaryPassword"], "newPassword": "reviewer-pass-123456"},
    )
    assert (await reviewer.get("/admin/verify/queue")).status_code == 200

    r = await super_admin.patch(f"/admin/admins/{admin_id}", json={"status": "disabled"})
    assert r.status_code == 200, r.text
    assert (await reviewer.get("/admin/verify/queue")).status_code == 401

    fresh = make_client()
    assert (await fresh.post("/admin/login", json={"email": email, "password": "reviewer-pass-123456"})).status_code in (401, 403)


# ── Reviewing the work ───────────────────────────────────────────────


async def test_e2e_adm_200_dashboard_counts_follow_the_queue(make_client, admin_client, counter):
    """E2E-ADM-200: the numbers ops looks at move as businesses move."""
    before = (await admin_client.get("/admin/dashboard/stats")).json()

    draft = await sign_up(make_client, counter, prefix="adm200d")
    pending = await _submitted(make_client, counter, prefix="adm200p")

    mid = (await admin_client.get("/admin/dashboard/stats")).json()
    assert mid["totalUsers"] == before["totalUsers"] + 2
    assert mid["draftBusinesses"] == before["draftBusinesses"] + 1
    assert mid["pendingVerificationBusinesses"] == before["pendingVerificationBusinesses"] + 1
    assert mid["recentSignups24H"] >= 2

    await admin_verify(admin_client, pending)
    after = (await admin_client.get("/admin/dashboard/stats")).json()
    assert after["verifiedBusinesses"] == before["verifiedBusinesses"] + 1
    assert after["pendingVerificationBusinesses"] == before["pendingVerificationBusinesses"]

    # The timeline is one point per day and never negative.
    timeline = (await admin_client.get("/admin/dashboard/timeline?days=7")).json()
    assert len(timeline) == 7 and all(point["count"] >= 0 for point in timeline)
    assert draft.user_id in [row["userId"] for row in (await admin_client.get("/admin/users")).json()["items"]]


async def test_e2e_adm_210_document_review_and_the_audit_trail(make_client, admin_client, counter):
    """E2E-ADM-210: ops opens a KYB file, reveals the number, rejects the
    entry and approves it later — every step lands in the audit log."""
    t = await _submitted(make_client, counter, prefix="adm210")
    entries = (await t.client.get("/me/verification-docs")).json()
    gstin = [e for e in entries if e["documentTypeCode"] == "gstin"][0]

    # It's waiting in the pending list.
    pending = (await admin_client.get("/admin/docs/pending")).json()
    row = [r for r in pending if r["doc"]["id"] == gstin["id"]]
    assert row, "the entry must be in the review queue"
    assert row[0]["userEmail"] == t.email and row[0]["businessId"] == t.business_id

    # Reveal the full number (the trader only ever sees it masked in lists).
    assert gstin["valueMasked"] and gstin["valueMasked"] != gstin["id"]
    revealed = await admin_client.post(f"/admin/docs/{gstin['id']}/reveal")
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["value"].endswith("1Z5")

    # Reject it with a reason; the trader is emailed and sees the reason.
    r = await admin_client.post(f"/admin/docs/{gstin['id']}/reject", json={"reason": "Scan is cut off."})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    mine = {e["id"]: e for e in (await t.client.get("/me/verification-docs")).json()}
    assert mine[gstin["id"]]["status"] == "rejected"
    assert mine[gstin["id"]]["rejectionReason"] == "Scan is cut off."
    assert [m for m in sent_emails(t.email) if "not accepted" in m.subject]

    # The trader replaces the file; it goes back to review and is approved.
    r = await t.client.patch(
        f"/me/verification-docs/{gstin['id']}", files={"file": ("gstin.pdf", PDF_BYTES, "application/pdf")}
    )
    assert r.status_code == 200 and r.json()["status"] != "rejected"
    assert (await admin_client.get(f"/admin/docs/{gstin['id']}/file")).status_code == 200
    r = await admin_client.post(f"/admin/docs/{gstin['id']}/approve")
    assert r.status_code == 200 and r.json()["status"] == "approved"

    logged = {a.action for a in await _actions()}
    assert {"kyb.value_viewed", "kyb.file_viewed", "doc.reject", "doc.approve"} <= logged
    # The audit trail never stores the number itself.
    for action in await _actions():
        assert "1Z5" not in str(action.details or {})


async def test_e2e_adm_220_business_decisions_are_audited(make_client, admin_client, counter):
    """E2E-ADM-220: approve and reject are both written to admin_actions with
    the reason ops gave."""
    t = await _submitted(make_client, counter, prefix="adm220")
    from flows import admin_reject

    await admin_reject(admin_client, t, reason="Address does not match the licence.", items=["addressLine"])
    rejects = await _actions("business.reject")
    assert rejects and rejects[-1].reason == "Address does not match the licence."
    assert rejects[-1].details["failed_items"] == ["addressLine"]

    await submit(t)
    await admin_verify(admin_client, t)
    assert await _actions("business.verify")


async def test_e2e_adm_230_ops_can_correct_a_profile(make_client, admin_client, counter):
    """E2E-ADM-230: ops edits a business field; the trader sees the change and
    the edit is on the record."""
    t = await _submitted(make_client, counter, prefix="adm230")
    r = await admin_client.patch(f"/admin/users/{t.user_id}", json={"businessProfile": {"city": "Panipat"}})
    assert r.status_code == 200, r.text

    me = (await t.client.get("/me")).json()
    assert me["business"]["city"] == "Panipat"
    assert await _actions("business.update")


async def test_e2e_adm_240_stuck_signups_surface_for_follow_up(make_client, admin_client, counter):
    """E2E-ADM-240: the "stuck" list only holds businesses that have been in
    draft long enough to chase — a brand-new one is not on it."""
    t = await sign_up(make_client, counter, prefix="adm240")
    stuck = (await admin_client.get("/admin/dashboard/stuck")).json()
    assert t.user_id not in [row["userId"] for row in stuck]

    import uuid
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.time import utcnow
    from app.models.business import Business

    async with SessionLocal() as db:
        await db.execute(
            update(Business)
            .where(Business.id == uuid.UUID(t.business_id))
            .values(created_at=utcnow() - timedelta(days=3))
        )
        await db.commit()

    stuck = (await admin_client.get("/admin/dashboard/stuck")).json()
    row = [r for r in stuck if r["userId"] == t.user_id]
    assert row and row[0]["hoursWaiting"] >= 24
