"""QA-600 / 700 — One review for profile + documents; the trader's view of a
rejection (adapted).

Keys are ``kyb:<code>`` for listed documents (Pegan: ``doc:<slug>``) and
``doc:<entry id>`` for "Other". ``rejectedItemLabels`` is a list aligned
with ``rejectedItems`` (Pegan: a map of doc keys only). Adapted on purpose:
unknown keys are refused with 400 instead of silently dropped.
"""
from __future__ import annotations

from conftest import fill_mandatory, signup_and_login
from qa_helpers import admin_add_doc_type, uniq, uniq_code, upload_entry, user_id_for


async def _ready_business(client, admin_client) -> tuple[str, dict]:
    """Profile + GSTIN/PAN + one extra required file document, submitted."""
    email = f"{uniq('qa6')}@test.cor1x.co"
    await signup_and_login(client, email)
    await fill_mandatory(client)
    code = uniq_code("qa6doc")
    t = await admin_add_doc_type(admin_client, code=code, name="QA6 cert")
    entry = await upload_entry(client, type_id=t["id"])
    assert (await client.post("/me/submit-verification")).status_code == 200
    return email, {"code": code, "type": t, "entry": entry}


# QA-600.1 — approve verifies the business and approves its required documents
async def test_approve_cascades_to_required_docs(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    r = await admin_client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert (await client.get("/me")).json()["verification"]["status"] == "verified"
    docs = [d for d in (await client.get("/me/verification-docs")).json() if d["documentTypeCode"] == ctx["code"]]
    assert len(docs) == 1 and docs[0]["status"] == "approved"


# QA-600.2 / 600.3 / 700 — reject with items: flags, labels, documents rejected
async def test_reject_with_items_cascades(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    r = await admin_client.post(
        f"/admin/users/{uid}/reject",
        json={"reason": "Legal name doesn't match the cert; cert image too dark.", "failedItems": ["legalName", f"kyb:{ctx['code']}"]},
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    v = (await client.get("/me")).json()["verification"]
    assert v["status"] == "rejected" and "Legal name doesn" in v["rejectedReason"]
    assert v["rejectedItems"] == ["legalName", f"kyb:{ctx['code']}"]
    assert v["rejectedItemLabels"] == ["Company name", "QA6 cert"]
    doc = next(d for d in (await client.get("/me/verification-docs")).json() if d["documentTypeCode"] == ctx["code"])
    assert doc["status"] == "rejected" and "Legal name doesn" in doc["rejectionReason"]


# QA-600.4 — reject with no items → 422, nothing changes (QA-F001)
async def test_reject_with_empty_failed_items_is_rejected(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    r = await admin_client.post(f"/admin/users/{uid}/reject", json={"reason": "no items", "failedItems": []})
    assert r.status_code == 422
    assert (await client.get("/me")).json()["verification"]["status"] == "pending_verification"


# QA-600.5 (adapted) — unknown keys are refused, nothing changes
async def test_reject_unknown_keys_refused(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    r = await admin_client.post(
        f"/admin/users/{uid}/reject", json={"reason": "mix of good + bogus keys", "failedItems": ["legalName", "someUnknownKey"]}
    )
    assert r.status_code == 400 and "someUnknownKey" in r.json()["detail"]
    assert (await client.get("/me")).json()["verification"]["status"] == "pending_verification"


# QA-600.6 — an already-rejected business can't be rejected again
async def test_cant_reject_already_rejected(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    body = {"reason": "first", "failedItems": ["legalName"]}
    assert (await admin_client.post(f"/admin/users/{uid}/reject", json=body)).status_code == 200
    assert (await admin_client.post(f"/admin/users/{uid}/reject", json=body)).status_code == 409


# QA-600.7 — a trader session can't verify or reject
async def test_non_admin_cant_verify_reject(client, admin_client):
    email, _ = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    assert (await client.post(f"/admin/users/{uid}/verify")).status_code == 401
    r = await client.post(f"/admin/users/{uid}/reject", json={"reason": "x", "failedItems": ["legalName"]})
    assert r.status_code == 401


# QA-600.8 — queue documents carry the type code and name
async def test_verify_queue_docs_carry_type_metadata(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    row = next(q for q in (await admin_client.get("/admin/verify/queue")).json() if q["userId"] == uid)
    cert = next(d for d in row["docs"] if d["documentTypeCode"] == ctx["code"])
    assert cert["certType"] == "QA6 cert" and cert["isOther"] is False


# QA-700.1 — a flagged document counts as missing until it is replaced
async def test_rejected_doc_counts_as_missing_until_replaced(client, admin_client):
    email, ctx = await _ready_business(client, admin_client)
    uid = await user_id_for(admin_client, email)
    await admin_client.post(f"/admin/users/{uid}/reject", json={"reason": "cert illegible", "failedItems": [f"kyb:{ctx['code']}"]})
    assert f"kyb:{ctx['code']}" in (await client.get("/me")).json()["verification"]["missing"]
