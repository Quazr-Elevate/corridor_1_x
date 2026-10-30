"""QA-600 / 700 — Single-review flow + trader-side rejection state."""
from __future__ import annotations

import pytest

from tests.conftest import fill_mandatory, signup_and_login
from tests.qa.conftest import (
    admin_add_requirement,
    uniq,
    upload_slot_doc,
)


async def _ready_business(client, admin_client, *, country: str = "IN") -> tuple[str, dict]:
    """Fully-filled business, submitted, with ONE mandatory doc attached.
    Returns (email, submit_response)."""
    email = f"{uniq('qa6')}@test.cor1x.co"
    await signup_and_login(client, email, country=country)
    await fill_mandatory(client)
    slug = uniq("qa6doc").replace("-", "_")
    req = await admin_add_requirement(admin_client, country=country, slug=slug, display_name="QA6 cert")
    await upload_slot_doc(client, slot_id=req["id"], slug=slug)
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200
    return email, {"state": r.json(), "slug": slug, "req": req}


async def _user_id_for(admin_client, email: str) -> str:
    r = await admin_client.get(f"/admin/users?q={email}")
    assert r.status_code == 200
    items = r.json()["items"]
    hits = [i for i in items if i["email"] == email]
    assert hits, f"user not in admin list: {email}"
    return hits[0]["userId"]


# QA-600.1 — approve cascades: business verified + cert doc approved
async def test_approve_cascades_to_cert_docs(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    r = await admin_client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"
    # Trader side: biz verified
    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "verified"
    # Mandatory cert doc now approved too (cascade)
    r = await client.get("/me/verification-docs")
    docs = [d for d in r.json() if d["requirementSlug"] == ctx["slug"]]
    assert len(docs) == 1 and docs[0]["status"] == "approved"


# QA-600.2 — reject with failed_items writes items + cascades doc rejection
async def test_reject_with_items_cascades(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    r = await admin_client.post(
        f"/admin/users/{uid}/reject",
        json={
            "reason": "Legal name doesn't match the cert; cert image too dark.",
            "failedItems": ["legalName", f"doc:{ctx['slug']}"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    # Trader side
    me = (await client.get("/me")).json()
    v = me["verification"]
    assert v["status"] == "rejected"
    assert "Legal name doesn" in v["rejectedReason"]
    assert set(v["rejectedItems"]) == {"legalName", f"doc:{ctx['slug']}"}
    # QA-700: labels only contain doc:*
    assert v["rejectedItemLabels"] == {f"doc:{ctx['slug']}": "QA6 cert"}
    # QA-600.3: cert doc now rejected with same reason
    docs = (await client.get("/me/verification-docs")).json()
    doc = next(d for d in docs if d["requirementSlug"] == ctx["slug"])
    assert doc["status"] == "rejected"
    assert "Legal name doesn" in doc["rejectionReason"]


# QA-600.4 — reject with empty failed_items is rejected (QA-F001 fix)
async def test_reject_with_empty_failed_items_is_rejected(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    r = await admin_client.post(
        f"/admin/users/{uid}/reject", json={"reason": "no items", "failedItems": []}
    )
    assert r.status_code == 422
    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "pending_verification"


# QA-600.5 — reject with unknown field key silently drops it (not an error)
async def test_reject_unknown_keys_silently_dropped(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    r = await admin_client.post(
        f"/admin/users/{uid}/reject",
        json={
            "reason": "mix of good + bogus keys",
            "failedItems": ["legalName", "someUnknownKey", "doc:nonexistent_slug"],
        },
    )
    assert r.status_code == 200
    me = (await client.get("/me")).json()
    # Backend keeps 'doc:*' keys even if slug doesn't exist; filters unknown bare keys.
    assert "legalName" in me["verification"]["rejectedItems"]
    assert "someUnknownKey" not in me["verification"]["rejectedItems"]


# QA-600.6 — can't reject an already-rejected business (idempotency guard)
async def test_cant_reject_already_rejected(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    first = await admin_client.post(
        f"/admin/users/{uid}/reject", json={"reason": "first", "failedItems": ["legalName"]}
    )
    assert first.status_code == 200
    second = await admin_client.post(
        f"/admin/users/{uid}/reject", json={"reason": "again", "failedItems": ["legalName"]}
    )
    assert second.status_code == 409


# QA-600.7 — non-admin can't call verify/reject
async def test_non_admin_cant_verify_reject(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    # trader client has user session, not admin
    r = await client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 401
    r = await client.post(f"/admin/users/{uid}/reject", json={"reason": "x", "failedItems": ["legalName"]})
    assert r.status_code == 401


# QA-600.8 — verify_queue carries requirementSlug + requirementDisplayName on docs
async def test_verify_queue_docs_carry_requirement_metadata(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    queue = (await admin_client.get("/admin/verify/queue")).json()
    row = next(q for q in queue if q["userId"] == uid)
    cert = next(d for d in row["docs"] if d["requirementSlug"] == ctx["slug"])
    assert cert["requirementDisplayName"] == "QA6 cert"


# QA-700.1 — missing[] re-includes rejected doc keys so resubmit still gates
async def test_rejected_doc_counts_as_missing_until_replaced(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await _user_id_for(admin_client, email)
    await admin_client.post(
        f"/admin/users/{uid}/reject",
        json={"reason": "cert illegible", "failedItems": [f"doc:{ctx['slug']}"]},
    )
    me = (await client.get("/me")).json()
    assert f"doc:{ctx['slug']}" in me["verification"]["missing"]
