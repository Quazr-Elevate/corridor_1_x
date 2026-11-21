from __future__ import annotations

from conftest import ADMIN_EMAIL, fill_mandatory, sent_emails, signup_and_login, verify_business
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.admin_action import AdminAction


async def _actions():
    """The decisions; list pages' identity.listed rows are tested in test_masking."""
    async with SessionLocal() as db:
        return list(
            await db.scalars(
                select(AdminAction).where(AdminAction.action != "identity.listed").order_by(AdminAction.created_at)
            )
        )


async def test_admin_login_and_auth(make_client):
    c = make_client()
    assert (await c.get("/admin/me")).status_code == 401
    r = await c.post("/admin/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert r.status_code == 401
    r = await c.post("/admin/login", json={"email": ADMIN_EMAIL.upper(), "password": "admin-pass-123"})
    assert r.status_code == 200
    me = (await c.get("/admin/me")).json()
    assert me["email"] == ADMIN_EMAIL and me["role"] == "super_admin" and me["mustChangePassword"] is False
    await c.post("/admin/logout")
    assert (await c.get("/admin/me")).status_code == 401


async def test_admin_login_rate_limited(make_client):
    c = make_client()
    codes = [
        (await c.post("/admin/login", json={"email": ADMIN_EMAIL, "password": "x"})).status_code for _ in range(11)
    ]
    assert codes[-1] == 429 and codes[:10] == [401] * 10


async def test_verify_flow_with_audit_and_email(client, admin_client):
    email = "v1@kaverifoods.in"
    body = await signup_and_login(client, email)
    uid = body["userId"]

    bid = body["businessId"]

    # Not submitted yet → 409
    r = await verify_business(admin_client, uid)
    assert r.status_code == 409
    assert "awaiting verification" in r.json()["detail"]

    await fill_mandatory(client)
    assert (await client.post("/me/submit-verification")).status_code == 200
    queue = (await admin_client.get("/admin/verify/queue")).json()["items"]
    assert [(row["userId"], row["businessId"]) for row in queue] == [(uid, bid)]
    assert queue[0]["country"] == "IN" and queue[0]["missingFields"] == []

    # Reject needs a reason.
    r = await admin_client.post(f"/admin/users/{uid}/reject", json={"reason": "   ", "failedItems": ["addressLine"]})
    assert r.status_code == 400
    r = await admin_client.post(f"/admin/users/{uid}/reject", json={"reason": "Upload your GST certificate", "failedItems": ["addressLine"]})
    assert r.status_code == 200 and r.json() == {"userId": uid, "businessId": bid, "status": "rejected"}
    rejected_mail = [m for m in sent_emails(email) if "needs changes" in m.subject]
    assert rejected_mail and "Upload your GST certificate" in rejected_mail[0].text
    me = (await client.get("/me")).json()
    assert me["verification"]["rejectedReason"] == "Upload your GST certificate"

    # Admin can approve from rejected.
    r = await verify_business(admin_client, uid)
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert any("verified" in m.subject for m in sent_emails(email))
    me = (await client.get("/me")).json()
    assert me["status"] == "verified" and me["verification"]["verifiedAt"]

    # Already verified → verify again is 409; reject (revoke) allowed.
    assert (await verify_business(admin_client, uid)).status_code == 409

    # The decisions (opening the account and its documents is audited too).
    actions = [a for a in await _actions() if a.action.startswith("business.")]
    assert [(a.action, a.target_type, a.target_id) for a in actions] == [
        ("business.reject", "business", bid),
        ("business.verify", "business", bid),
    ]
    assert actions[0].reason == "Upload your GST certificate"
    assert actions[0].admin_email == ADMIN_EMAIL

    detail = (await admin_client.post(f"/admin/users/{uid}/open", json={"reason": "KYB review of this business"})).json()
    assert detail["businessId"] == bid and detail["role"] == "owner" and detail["status"] == "verified"


async def test_verify_requires_mandatory_fields(client, admin_client):
    body = await signup_and_login(client, "v2@kaverifoods.in")
    await fill_mandatory(client)
    await client.post("/me/submit-verification")
    # Admin blanks a required profile field, then tries to approve.
    r = await admin_client.patch(f"/admin/users/{body['userId']}", json={"businessProfile": {"addressLine": ""}})
    assert r.status_code == 200, r.text
    assert r.json()["missingMandatoryFields"] == ["addressLine"]
    r = await verify_business(admin_client, body['userId'])
    assert r.status_code == 400
    assert "Registered address" in r.json()["detail"]


async def test_admin_patch_typed_and_unique(client, make_client, admin_client):
    a = await signup_and_login(client, "pa@kaverifoods.in")
    await fill_mandatory(client, n=1)
    other = make_client()
    b = await signup_and_login(other, "pb@othermill.in")
    await fill_mandatory(other, n=2)

    r = await admin_client.patch(f"/admin/users/{b['userId']}", json={"businessProfile": {"pincode": "12AB"}})
    assert r.status_code == 422
    r = await admin_client.patch(
        f"/admin/users/{b['userId']}", json={"businessProfile": {"tradePosition": "pirate"}}
    )
    assert r.status_code == 422
    r = await admin_client.patch(f"/admin/users/{b['userId']}", json={"businessProfile": {"country": "Narnia"}})
    assert r.status_code == 422
    # A shared company name is allowed and flagged, not refused (A-046).
    r = await admin_client.patch(
        f"/admin/users/{b['userId']}", json={"businessProfile": {"legalName": "ACME AGRO 1 PVT LTD"}}
    )
    assert r.status_code == 200 and r.json()["sameNameAs"]
    r = await admin_client.patch(f"/admin/users/{b['userId']}", json={"profile": {"phone": "+91 98765 00001"}})
    assert r.status_code == 409

    # A field the API does not know is refused, and nothing is saved.
    r = await admin_client.patch(
        f"/admin/users/{b['userId']}",
        json={"businessProfile": {"industry": "Spices", "bankAccountNumber": "XXXX1234"}},
    )
    assert r.status_code == 422 and r.json()["code"] == "request.unknown_field"
    assert r.json()["fields"] == [
        {"field": "businessProfile.bankAccountNumber", "message": "This field is not accepted."}
    ]

    r = await admin_client.patch(
        f"/admin/users/{b['userId']}",
        json={
            "profile": {"position": "CEO"},
            # Address / socials / country are business fields now.
            "businessProfile": {
                "industry": "Spices",
                "city": "Pune",
                "pincode": "411001",
                "country": "ae",
                "entityType": "llp",
            },
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["businessId"] == b["businessId"]
    assert d["profile"] == {"fullName": "Asha Rao", "phone": "+91 98765 00002", "position": "CEO"}
    bp = d["businessProfile"]
    assert (bp["industry"], bp["city"], bp["pincode"], bp["country"], bp["entityType"]) == (
        "Spices", "Pune", "411001", "AE", "llp"
    )
    actions = await _actions()
    # The PATCH answers with the account detail, so the edit is followed by
    # the audit row for opening that company's identity.
    assert [a.action for a in actions[-2:]] == ["business.update", "identity.unmasked"]
    assert actions[-1].target_id == b["businessId"] and actions[-1].details["purpose"] == "account_edit"
    actions = actions[:-1]
    assert actions[-1].target_type == "business" and actions[-1].target_id == b["businessId"]
    assert set(actions[-1].details["fields"]) == {
        "profile.position",
        "businessProfile.industry",
        "businessProfile.city",
        "businessProfile.pincode",
        "businessProfile.country",
        "businessProfile.entity_type",
    }

    assert (await admin_client.post(f"/admin/users/{a['userId']}/open", json={"reason": "KYB review of this business"})).status_code == 200
    r = await admin_client.post("/admin/users/not-a-uuid/open", json={"reason": "KYB review of this business"})
    assert r.status_code == 404


async def test_dashboard(client, admin_client):
    await signup_and_login(client, "dash@kaverifoods.in")
    stats = (await admin_client.get("/admin/dashboard/stats")).json()
    assert stats == {
        "totalUsers": 1,
        "totalBusinesses": 1,
        "draftBusinesses": 1,
        "pendingVerificationBusinesses": 0,
        "verifiedBusinesses": 0,
        "rejectedBusinesses": 0,
        "totalProducts": 0,
        "recentSignups24H": 1,
        "stuckSignups": 0,
        "pendingDocs": 0,
    }
    tl = (await admin_client.get("/admin/dashboard/timeline?days=7")).json()
    assert len(tl) == 7 and tl[-1]["count"] == 1
    assert (await admin_client.get("/admin/dashboard/stuck")).json()["items"] == []
    users = (await admin_client.get("/admin/users?q=dash")).json()
    assert users["total"] == 1 and users["items"][0]["status"] == "draft"
    assert (await admin_client.get("/admin/users?status=draft")).json()["total"] == 1
    assert (await admin_client.get("/admin/users?status=verified")).json()["total"] == 0
    assert (await admin_client.get("/admin/users?status=email_verified")).status_code == 400
