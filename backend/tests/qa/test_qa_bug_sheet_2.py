"""Issues from the team's bug sheet ("corridor 1x bug", 26 Nov 2026), one
test per issue the backend can prove. #1 and the dropdown colours are screen
fixes; #6's calendar limits are in the form."""
from __future__ import annotations

from conftest import fill_mandatory, set_status, signup_and_login, verify_business
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.admin_action import AdminAction
from app.models.business import BusinessStatus

WHY = {"reason": "Changing the business's country"}


async def test_3_staff_can_remove_a_document_and_then_change_the_country(client, admin_client):
    me = await signup_and_login(client, "s3@kaverifoods.in")
    await fill_mandatory(client)
    assert (await client.post("/me/submit-verification")).status_code == 200
    assert (await verify_business(admin_client, me["userId"])).status_code == 200
    r = await admin_client.patch(f"/admin/users/{me['userId']}", json={"businessProfile": {"country": "AE"}})
    assert r.status_code == 400 and "Documents, below" in r.json()["detail"]

    docs = (await client.get("/me/verification-docs")).json()["items"]
    assert (await admin_client.post(f"/admin/docs/{docs[0]['id']}/remove", json={})).status_code == 422
    for d in docs:
        assert (await admin_client.post(f"/admin/docs/{d['id']}/remove", json=WHY)).status_code == 204
    assert (await client.get("/me/verification-docs")).json()["items"] == []
    me_now = (await client.get("/me")).json()
    assert me_now["status"] == "pending_verification"  # a required document went: back to review

    r = await admin_client.patch(f"/admin/users/{me['userId']}", json={"businessProfile": {"country": "AE"}})
    assert r.status_code == 200 and r.json()["businessProfile"]["country"] == "AE"
    async with SessionLocal() as db:
        removed = list(await db.scalars(select(AdminAction).where(AdminAction.action == "kyb.entry_removed")))
    assert len(removed) == len(docs) and removed[0].reason == WHY["reason"]


async def test_3_removing_needs_the_edit_permission(client, make_client, admin_client):
    from test_admin_accounts import _new_admin

    await signup_and_login(client, "s3b@kaverifoods.in")
    await fill_mandatory(client)
    doc = (await client.get("/me/verification-docs")).json()["items"][0]
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    assert (await desk.post(f"/admin/docs/{doc['id']}/remove", json=WHY)).status_code == 403
    assert (await make_client().post(f"/admin/docs/{doc['id']}/remove", json=WHY)).status_code == 401


async def test_4_a_short_number_is_judged_by_the_type_not_by_the_code(client):
    await signup_and_login(client, "s4@kaverifoods.in")
    # "Other" documents have no format of their own: any length is the business's call.
    r = await client.post("/me/verification-docs", data={"customName": "Spices Board", "value": "SB1"})
    assert r.status_code == 201, r.text


async def test_5_the_dashboard_counts_only_documents_waiting_for_a_reviewer(client, make_client, admin_client):
    draft = await signup_and_login(client, "s5a@kaverifoods.in")
    await fill_mandatory(client)  # two documents, business still a draft
    stats = (await admin_client.get("/admin/dashboard/stats")).json()
    assert stats["pendingDocs"] == 0
    assert (await admin_client.get("/admin/docs/pending")).json()["items"] == []

    assert (await client.post("/me/submit-verification")).status_code == 200
    assert (await admin_client.get("/admin/dashboard/stats")).json()["pendingDocs"] == 2
    queue = (await admin_client.get("/admin/verify/queue")).json()["items"]
    assert sum(len(r["docs"]) for r in queue) == 2

    await set_status(draft["userId"], BusinessStatus.rejected)
    assert (await admin_client.get("/admin/dashboard/stats")).json()["pendingDocs"] == 0


async def test_6_past_delivery_dates_are_refused_when_saved(client):
    me = await signup_and_login(client, "s6@kaverifoods.in")
    await set_status(me["userId"], BusinessStatus.verified)
    rfq = (await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "Basmati"})).json()
    r = await client.patch(f"/rfqs/{rfq['id']}", json={"deliveryFrom": "2020-01-01"})
    assert r.status_code == 400 and "can't be in the past" in r.json()["detail"]
