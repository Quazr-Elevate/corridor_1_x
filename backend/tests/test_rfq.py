"""RFQs (CX-090, CX-092, CX-093, CX-094): drafts, the paid submit, the hard
matching rules, the desk's triage, what a seller sees, refunds and expiry."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from conftest import complete_listing, fill_mandatory, publish_listing, sent_emails, set_status, signup_and_login
from sqlalchemy import select, update
from test_admin_accounts import _new_admin

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models import AdminAction, BusinessStatus, CreditLedgerEntry, Deal, DealEvent, Rfq, RfqMatch
from app.modules.rfq import matching
from app.modules.rfq import service as rfqs

TODAY = utcnow().date()
WINDOW = {"deliveryFrom": (TODAY + timedelta(days=30)).isoformat(), "deliveryTo": (TODAY + timedelta(days=60)).isoformat()}


async def _template(c, category="Rice") -> dict:
    return (await c.get("/public/catalog/template", params={"category": category})).json()


async def _limits(c, **over) -> list[dict]:
    """A limit for every required rice parameter that a value of 5 satisfies."""
    rows = []
    for p in (await _template(c))["specParameters"]:
        if p["isRequired"]:
            value = over.get(p["code"], "12" if p["defaultOperator"] == "MAX" else "4")
            rows.append({"parameterId": p["id"], "value": value})
    return rows


async def _body(c, **over) -> dict:
    body = {
        "kind": "open", "category": "Rice", "productName": "1121 Steam Basmati", "quantity": "500", "unit": "MT",
        "incoterms": ["FOB"], "paymentTerms": "lc_sight", "deliveryCountry": "AE", "destinationPort": "Jebel Ali",
        "targetPriceMin": 7000000, "targetPriceMax": 7800000, "currency": "INR", "packaging": "50 kg PP bags",
        "notes": "Sortex cleaned, 2026 crop.", "specs": await _limits(c), **WINDOW,
    }
    body.update(over)
    return body


async def _buyer(c, email="buyer@gulfgrain.ae", *, n=3, verified=True) -> dict:
    who = await signup_and_login(c, email)
    await fill_mandatory(c, n=n)  # a registration number, so the free RFQs apply
    if verified:
        await set_status(who["userId"], BusinessStatus.verified)
    return who


async def _seller(c, admin, email="seller@kaverifoods.in", **listing) -> tuple[dict, str]:
    who = await signup_and_login(c, email)
    await set_status(who["userId"], BusinessStatus.verified)
    pid = (await complete_listing(c, **listing))["id"]
    await publish_listing(c, admin, pid)
    return who, pid


def _match_mails(to: str) -> list:
    return [m for m in sent_emails(to) if m.subject == "A buyer request matches your listing"]


async def _submitted(buyer, **over) -> dict:
    r = await buyer.post("/rfqs", json=await _body(buyer, **over))
    assert r.status_code == 201, r.text
    r = await buyer.post(f"/rfqs/{r.json()['id']}/submit")
    assert r.status_code == 200, r.text
    return r.json()


# ── Drafts ───────────────────────────────────────────────────────────


async def test_a_draft_needs_little_and_says_what_is_missing(client, make_client):
    assert (await make_client().post("/rfqs", json={"kind": "open"})).status_code == 401
    await signup_and_login(client, "buyer@gulfgrain.ae")
    assert (await client.post("/rfqs", json={"kind": "open"})).status_code == 400  # no category or name
    r = await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "Basmati"})
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["tracking"] == "draft" and draft["dealCode"] is None
    assert draft["missing"][:5] == [
        "the quantity", "the delivery country", "the delivery window", "at least one incoterm",
        "how you would like to pay",
    ]
    assert any(m.startswith("your limit for") for m in draft["missing"])

    r = await client.patch(f"/rfqs/{draft['id']}", json={"quantity": "500", "status": "matched"})
    assert r.status_code == 422 and r.json()["code"] == "request.unknown_field"  # status is never a field
    r = await client.patch(f"/rfqs/{draft['id']}", json={"targetPriceMax": 10})
    assert r.status_code == 400  # an upper price with no lower one
    past = {"deliveryFrom": "2020-01-01", "deliveryTo": "2020-02-01"}
    r = await client.patch(f"/rfqs/{draft['id']}", json=past)
    assert r.status_code == 400 and "can't be in the past" in r.json()["detail"]  # bug sheet #6: on save
    r = await client.patch(f"/rfqs/{draft['id']}", json={"notes": "call me on 98765 43210"})
    assert r.status_code == 400 and "phone number" in r.json()["detail"]
    assert (await client.delete(f"/rfqs/{draft['id']}")).status_code == 204
    assert (await client.get(f"/rfqs/{draft['id']}")).status_code == 404


async def test_another_business_cannot_read_change_or_submit_my_rfq(client, make_client):
    await signup_and_login(client, "buyer@gulfgrain.ae")
    rid = (await client.post("/rfqs", json=await _body(client))).json()["id"]
    other = make_client()
    await _buyer(other, "second@othermill.in", n=4)
    for call in (
        other.get(f"/rfqs/{rid}"), other.patch(f"/rfqs/{rid}", json={"quantity": "1"}),
        other.post(f"/rfqs/{rid}/submit"), other.delete(f"/rfqs/{rid}"), other.get(f"/rfqs/{rid}/seller-preview"),
    ):
        assert (await call).status_code == 404
    assert (await other.get("/rfqs")).json()["total"] == 0
    assert (await client.get("/rfqs/not-a-uuid")).status_code == 404


# ── Submit ───────────────────────────────────────────────────────────


async def test_submit_needs_verification_then_opens_a_deal_and_uses_a_free_rfq(client):
    me = await _buyer(client, verified=False)
    rid = (await client.post("/rfqs", json=await _body(client))).json()["id"]
    r = await client.post(f"/rfqs/{rid}/submit")
    assert r.status_code == 403 and "draft is saved" in r.json()["detail"]
    assert (await client.get(f"/rfqs/{rid}")).json()["status"] == "draft"

    await set_status(me["userId"], BusinessStatus.verified)
    assert (await client.get("/rfqs/submit-cost")).json() == {"credits": 0, "free": True}
    r = await client.post(f"/rfqs/{rid}/submit")
    assert r.status_code == 200, r.text
    rfq = r.json()
    assert rfq["status"] == "submitted" and rfq["tracking"] == "awaiting" and rfq["missing"] == []
    assert rfq["dealCode"].startswith("DL-") and rfq["expiresAt"] is not None
    assert (await client.post(f"/rfqs/{rid}/submit")).status_code == 409  # not twice
    assert (await client.patch(f"/rfqs/{rid}", json={"quantity": "1"})).status_code == 409
    assert (await client.delete(f"/rfqs/{rid}")).status_code == 409

    wallet = (await client.get("/wallet")).json()
    assert wallet["freeRfqs"] == {"allowance": 10, "used": 1, "remaining": 9} and wallet["balance"] == 0
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == rfq["dealCode"]))
        assert deal.status == "RFQ_OPEN" and str(deal.buyer_business_id) == me["businessId"]
        (event,) = list(await db.scalars(select(DealEvent).where(DealEvent.deal_id == deal.id)))
        assert (event.action, event.actor_type, str(event.actor_id)) == ("rfq_submitted", "user", me["userId"])
        (line,) = list(await db.scalars(select(CreditLedgerEntry)))
        assert (line.entry_type, line.amount, line.free, line.reference_id) == ("RFQ_POST", 0, True, rid)
        stored = await db.get(Rfq, uuid.UUID(rid))
        assert (stored.expires_at - stored.submitted_at) == timedelta(days=14)


async def test_submit_is_refused_until_complete_and_charges_nothing(client):
    await _buyer(client)
    rid = (await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "Basmati"})).json()["id"]
    r = await client.post(f"/rfqs/{rid}/submit")
    assert r.status_code == 400 and r.json()["detail"].startswith("Before submitting, add the quantity")
    assert (await client.get("/wallet")).json()["freeRfqs"]["used"] == 0
    async with SessionLocal() as db:
        assert list(await db.scalars(select(Deal))) == []


async def test_without_a_free_rfq_or_credits_submit_is_402_and_nothing_is_created(client):
    me = await signup_and_login(client, "buyer@gulfgrain.ae")
    await set_status(me["userId"], BusinessStatus.verified)  # verified, but no registration number on file
    assert (await client.get("/rfqs/submit-cost")).json() == {"credits": 5, "free": False}
    rid = (await client.post("/rfqs", json=await _body(client))).json()["id"]
    r = await client.post(f"/rfqs/{rid}/submit")
    assert r.status_code == 402 and r.json()["code"] == "credits.insufficient"
    assert (await client.get(f"/rfqs/{rid}")).json()["status"] == "draft"
    async with SessionLocal() as db:
        assert list(await db.scalars(select(Deal))) == [] and list(await db.scalars(select(CreditLedgerEntry))) == []


# ── Matching rules ───────────────────────────────────────────────────


def test_within_compares_numbers_as_numbers_and_text_as_text():
    assert matching.within("5", "12", "MAX") and not matching.within("13", "12", "MAX")
    assert matching.within("8.3", "8", "MIN") and not matching.within("7.9", "8", "MIN")
    assert matching.within("5.0", "5", "EQ") and not matching.within("5.1", "5", "EQ")
    assert matching.within("Long  Grain", "long grain", "EQ") and not matching.within("short", "long", "EQ")
    assert not matching.within("long", "long", "MAX")  # text has no order


async def test_only_listings_that_meet_every_hard_rule_are_proposed(client, make_client, admin_client):
    fits, _ = await _seller(client, admin_client)
    small = make_client()
    # 100 MT in stock and 100 MT a month over the two months left: 300 MT against 500 asked.
    await _seller(small, admin_client, "small@tinymill.in", capacityPerMonth="100", quantity="100")
    slow = make_client()
    await _seller(slow, admin_client, "slow@latemill.in", leadTimeDays=90)  # the window closes in 60 days
    other = make_client()
    await _seller(other, admin_client, "spice@nairspice.in", category="Spices", name="Black pepper")
    buyer = make_client()
    await _buyer(buyer)

    rfq = await _submitted(buyer)
    detail = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()
    assert [m["status"] for m in detail["matches"]] == ["proposed"]
    match = detail["matches"][0]
    assert match["source"] == "rule" and match["sellerCode"] and match["sellerState"] is None
    assert [(r["rule"], r["ok"]) for r in match["reasons"]] == [
        ("category", True), ("capacity", True), ("specs", True), ("lead_time", True), ("incoterms", True),
        ("certificates", True),
    ]
    assert match["reasons"][1]["detail"] == "Capacity 2000 MT a month over 2 months and 500 MT in stock against 500 MT asked."

    # A grain-length limit the listing does not reach: nobody is proposed.
    strict = await _submitted(buyer, specs=await _limits(buyer, grain_length="9"))
    assert (await admin_client.get(f"/admin/rfqs/{strict['id']}")).json()["matches"] == []


async def test_the_buyers_own_listing_is_never_matched_to_their_rfq(client, admin_client):
    me = await _buyer(client)
    pid = (await complete_listing(client))["id"]
    await publish_listing(client, admin_client, pid)
    rfq = await _submitted(client)
    assert (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()["matches"] == []
    r = await admin_client.post(f"/admin/rfqs/{rfq['id']}/matches", json={"listingId": pid})
    assert r.status_code == 400 and "belongs to the buyer" in r.json()["detail"]
    r = await client.post("/rfqs", json={"kind": "listing", "listingId": pid})
    assert r.status_code == 400  # an RFQ on your own listing


async def test_an_rfq_from_a_listing_proposes_that_listing_only(client, make_client, admin_client):
    _, pid = await _seller(client, admin_client)
    second = make_client()
    await _seller(second, admin_client, "second@othermill.in")
    buyer = make_client()
    await _buyer(buyer)
    r = await buyer.post("/rfqs", json=await _body(buyer, kind="listing", listingId=pid, category=None, productName=None))
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "Rice" and r.json()["productName"] == "1121 Steam Basmati"
    assert (await buyer.post("/rfqs", json={"kind": "listing", "listingId": str(uuid.uuid4())})).status_code == 404
    rfq = (await buyer.post(f"/rfqs/{r.json()['id']}/submit")).json()
    matches = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()["matches"]
    assert [m["listingId"] for m in matches] == [pid]


# ── Desk ─────────────────────────────────────────────────────────────


async def test_nothing_reaches_a_seller_until_the_desk_confirms(client, make_client, admin_client):
    seller, _ = await _seller(client, admin_client)
    buyer = make_client()
    me = await _buyer(buyer)
    rfq = await _submitted(buyer)

    assert (await client.get("/matched-rfqs")).json() == {"total": 0, "items": []}
    assert (await client.post(f"/matched-rfqs/{rfq['id']}/open")).status_code == 404
    assert _match_mails("seller@kaverifoods.in") == []

    queue = (await admin_client.get("/admin/rfqs")).json()
    assert queue["total"] == 1
    row = queue["items"][0]
    assert (row["status"], row["proposed"], row["confirmed"], row["dealCode"]) == ("submitted", 1, 0, rfq["dealCode"])
    detail = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()
    # The desk works from codes: no name of either party anywhere on the screen.
    text = str(queue) + str(detail)
    assert "Trading" not in text and "gulfgrain" not in text and "kaverifoods" not in text
    assert detail["rfq"]["buyerCode"] == (await buyer.get("/me")).json()["companyCode"]
    assert (detail["targetPriceMin"], detail["targetPriceMax"], detail["currency"]) == (7000000, 7800000, "INR")

    r = await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")
    assert r.status_code == 200 and r.json() == {"id": rfq["id"], "status": "matched", "dealStatus": "RFQ_OPEN"}
    assert (await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")).status_code == 409
    assert (await admin_client.get("/admin/rfqs")).json()["total"] == 0  # off the pending queue
    assert (await admin_client.get("/admin/rfqs", params={"queue": "all"})).json()["items"][0]["confirmed"] == 1

    (mail,) = _match_mails("seller@kaverifoods.in")
    assert "Rice" in mail.text and "gulfgrain" not in mail.text.lower() and me["businessId"] not in mail.text
    inbox = (await client.get("/matched-rfqs")).json()
    assert inbox["total"] == 1 and inbox["items"][0]["opened"] is False and inbox["items"][0]["openCost"] == 1
    assert (await buyer.get(f"/rfqs/{rfq['id']}")).json()["tracking"] == "awaiting"

    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).where(AdminAction.action.like("rfq.%")))]
    assert actions == ["rfq.confirm"]


async def test_the_desk_adjusts_matches_but_cannot_break_a_hard_rule(client, make_client, admin_client):
    _, fits = await _seller(client, admin_client)
    small = make_client()
    _, too_small = await _seller(small, admin_client, "small@tinymill.in", capacityPerMonth="100", quantity="100")
    buyer = make_client()
    await _buyer(buyer)
    rfq = await _submitted(buyer)
    url = f"/admin/rfqs/{rfq['id']}"

    r = await admin_client.post(f"{url}/matches", json={"listingId": too_small})
    assert r.status_code == 409 and "Capacity 100 MT a month over 2 months against 500 MT asked." in r.json()["detail"]
    r = await admin_client.post(f"{url}/matches", json={"listingId": fits})
    assert r.status_code == 409 and "already matched" in r.json()["detail"]

    match = (await admin_client.get(url)).json()["matches"][0]
    assert (await admin_client.delete(f"{url}/matches/{match['id']}")).status_code == 204
    assert (await admin_client.delete(f"{url}/matches/{match['id']}")).status_code == 404
    assert (await admin_client.get(url)).json()["matches"] == []
    r = await admin_client.post(f"{url}/confirm")
    assert r.status_code == 409 and "no seller to confirm" in r.json()["detail"]

    r = await admin_client.post(f"{url}/matches", json={"listingId": fits})  # the desk puts it back
    assert r.status_code == 201 and r.json()["matches"][0]["source"] == "desk"
    assert (await admin_client.post(f"{url}/confirm")).status_code == 200
    assert (await admin_client.post(f"{url}/matches", json={"listingId": fits})).status_code == 409  # closed to changes


async def test_reject_and_no_match_refund_the_buyer_and_cancel_the_deal(client, admin_client):
    me = await _buyer(client)
    first = await _submitted(client)
    second = await _submitted(client)
    assert (await client.get("/wallet")).json()["freeRfqs"]["used"] == 2

    assert (await admin_client.post(f"/admin/rfqs/{first['id']}/reject", json={})).status_code == 422
    r = await admin_client.post(f"/admin/rfqs/{first['id']}/reject", json={"reason": "This is a test request, not a real order."})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["dealStatus"] == "CANCELLED"
    mine = (await client.get(f"/rfqs/{first['id']}")).json()
    assert mine["tracking"] == "rejected" and mine["rejectionReason"] == "This is a test request, not a real order."
    assert (await admin_client.post(f"/admin/rfqs/{first['id']}/confirm")).status_code == 409

    r = await admin_client.post(f"/admin/rfqs/{second['id']}/no-match")
    assert r.status_code == 200 and r.json()["status"] == "unmatched"
    assert (await client.get(f"/rfqs/{second['id']}")).json()["rejectionReason"] is None

    wallet = (await client.get("/wallet")).json()
    assert wallet["freeRfqs"] == {"allowance": 10, "used": 0, "remaining": 10}  # both free RFQs came back
    ledger = (await client.get("/wallet/ledger")).json()["items"]
    assert sorted((l["entryType"], l["amount"], l["free"]) for l in ledger) == [
        ("REVERSAL", 0, True), ("REVERSAL", 0, True), ("RFQ_POST", 0, True), ("RFQ_POST", 0, True),
    ]
    async with SessionLocal() as db:
        reasons = sorted(d.cancel_reason for d in await db.scalars(select(Deal)))
        assert reasons == ["No seller matched the request", "RFQ rejected by the desk"]
        last = (await db.scalars(select(DealEvent).order_by(DealEvent.created_at.desc()))).first()
        assert (last.action, last.actor_type) == ("cancelled", "admin")


async def test_an_rfq_touching_a_held_country_stops_for_the_desk(client, make_client, admin_client):
    await _seller(client, admin_client)
    buyer = make_client()
    await _buyer(buyer)
    assert (await admin_client.get("/admin/held-countries")).json() == {"total": 0, "items": []}  # starts empty
    assert (await admin_client.put("/admin/held-countries/a1", json={"reason": "Not a country"})).status_code == 400
    r = await admin_client.put("/admin/held-countries/ae", json={"reason": "Compliance review of UAE deliveries"})
    assert r.status_code == 200 and r.json()["code"] == "AE"

    rfq = await _submitted(buyer)
    assert rfq["status"] == "held" and rfq["tracking"] == "awaiting"
    detail = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()
    assert detail["deskReason"] == "AE: Compliance review of UAE deliveries"
    assert (await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")).status_code == 409  # not while held
    r = await admin_client.post(f"/admin/rfqs/{rfq['id']}/release", json={"reason": "End use checked with the buyer."})
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert (await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")).status_code == 200

    assert (await admin_client.delete("/admin/held-countries/AE")).status_code == 204
    assert (await admin_client.delete("/admin/held-countries/AE")).status_code == 404
    assert (await _submitted(buyer))["status"] == "submitted"


async def test_desk_roles_see_the_queue_and_nothing_else(client, admin_client, make_client):
    await _buyer(client)
    rfq = await _submitted(client)
    _, reviewer = await _new_admin(admin_client, make_client)
    assert (await reviewer.get("/admin/rfqs")).status_code == 403  # KYB reviewers do not work RFQs
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    me = (await desk.get("/admin/me")).json()
    assert me["role"] == "trade_desk" and set(me["permissions"]) == {"dashboard.view", "rfqs.triage", "samples.handle"}
    assert (await desk.get(f"/admin/rfqs/{rfq['id']}")).status_code == 200
    # The desk works from codes: no directory, no KYB, no unmask, no settings.
    for call in (
        desk.get("/admin/users"), desk.get("/admin/verify/queue"),
        desk.post("/admin/companies/IN-000000/unmask", json={"reason": "Curious about the buyer"}),
        desk.put("/admin/held-countries/AE", json={"reason": "I should not be able to"}),
        desk.put("/admin/trade-settings/rfq_open_days", json={"value": "1"}),
    ):
        assert (await call).status_code == 403
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="manager@cor1x.test")
    assert (await manager.get("/admin/rfqs")).status_code == 200
    assert (await client.get("/admin/rfqs")).status_code == 401  # a trader's session is not an admin's


# ── Seller ───────────────────────────────────────────────────────────


async def test_a_seller_pays_once_to_open_and_never_sees_the_price_or_the_buyer(client, make_client, admin_client, checkout=None):
    seller, _ = await _seller(client, admin_client)
    stranger = make_client()
    await _seller(stranger, admin_client, "small@tinymill.in", capacityPerMonth="100", quantity="100")  # not matched
    buyer = make_client()
    me = await _buyer(buyer)
    rfq = await _submitted(buyer)
    await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")

    assert (await stranger.post(f"/matched-rfqs/{rfq['id']}/open")).status_code == 404
    assert (await buyer.post(f"/matched-rfqs/{rfq['id']}/open")).status_code == 404
    r = await client.post(f"/matched-rfqs/{rfq['id']}/open")
    assert r.status_code == 402 and "This costs 1 credit and you have 0." in r.json()["detail"]

    async with SessionLocal() as db:
        from app.modules.credits import service as credits

        await credits._post(db, uuid.UUID(seller["businessId"]), "TOP_UP", 3, idempotency_key="test-top-up")
        await db.commit()
    r = await client.post(f"/matched-rfqs/{rfq['id']}/open")
    assert r.status_code == 200, r.text
    seen = r.json()
    preview = (await buyer.get(f"/rfqs/{rfq['id']}/seller-preview")).json()
    assert seen == preview  # the buyer's preview is exactly what the seller reads
    assert "targetPriceMin" not in seen and "currency" not in seen and "7000000" not in str(seen)
    assert seen["buyerCode"] == (await buyer.get("/me")).json()["companyCode"] and seen["buyerCountry"] == "IN"
    assert me["businessId"] not in str(seen) and "gulfgrain" not in str(seen).lower()
    assert seen["notes"] == "Sortex cleaned, 2026 crop." and seen["packaging"] == "50 kg PP bags"
    assert [s["code"] for s in seen["specs"]] and seen["quantity"] == "500.00"

    assert (await client.post(f"/matched-rfqs/{rfq['id']}/open")).status_code == 200  # again: free
    wallet = (await client.get("/wallet")).json()
    assert wallet["balance"] == 2
    row = (await client.get("/matched-rfqs")).json()["items"][0]
    assert row["opened"] is True and row["openCost"] == 0
    detail = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()
    assert detail["matches"][0]["viewedAt"] is not None


# ── Expiry and settings ──────────────────────────────────────────────


async def test_an_rfq_with_no_offer_expires_and_its_deal_is_cancelled(client, make_client, admin_client):
    await _seller(client, admin_client)
    buyer = make_client()
    await _buyer(buyer)
    rfq = await _submitted(buyer)
    await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")
    async with SessionLocal() as db:
        assert await rfqs.expire_due(db) == 0  # not yet
        await db.execute(update(Rfq).values(expires_at=utcnow() - timedelta(minutes=1)))
        await db.commit()

    mine = (await buyer.get("/rfqs")).json()["items"][0]  # reading the list runs the expiry
    assert (mine["status"], mine["tracking"]) == ("expired", "expired")
    assert (await client.get("/matched-rfqs")).json()["total"] == 0
    assert (await client.post(f"/matched-rfqs/{rfq['id']}/open")).status_code == 404
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal))
        assert (deal.status, deal.cancel_reason) == ("CANCELLED", "expired")
        last = (await db.scalars(select(DealEvent).order_by(DealEvent.created_at.desc()))).first()
        assert (last.action, last.actor_type, last.actor_id) == ("cancelled", "system", None)
        assert await rfqs.expire_due(db) == 0  # once
    # No seller quoted, so the free RFQ comes back (A-053).
    assert (await buyer.get("/wallet")).json()["freeRfqs"]["remaining"] == 10
    async with SessionLocal() as db:
        lines = [(l.entry_type, l.free) for l in await db.scalars(select(CreditLedgerEntry).order_by(CreditLedgerEntry.created_at))]
    assert lines == [("RFQ_POST", True), ("REVERSAL", True)]


async def test_trade_settings_are_placeholders_until_a_super_admin_sets_them(client, admin_client):
    settings = {s["key"]: s for s in (await admin_client.get("/admin/trade-settings")).json()["items"]}
    assert settings["rfq_open_days"] == {"key": "rfq_open_days", "value": "14.0000", "isPlaceholder": True}
    assert settings["min_margin_pct"]["isPlaceholder"] and settings["fx_buffer_pct"]["isPlaceholder"]
    assert settings["freight_max_age_days"] == {"key": "freight_max_age_days", "value": "7.0000", "isPlaceholder": False}

    assert (await admin_client.put("/admin/trade-settings/nope", json={"value": "1"})).status_code == 404
    assert (await admin_client.put("/admin/trade-settings/rfq_open_days", json={"value": "2.5"})).status_code == 400
    assert (await admin_client.put("/admin/trade-settings/rfq_open_days", json={"value": "-1"})).status_code == 422
    r = await admin_client.put("/admin/trade-settings/rfq_open_days", json={"value": "21"})
    assert r.status_code == 200 and r.json()["isPlaceholder"] is False

    await _buyer(client)
    rfq = await _submitted(client)
    async with SessionLocal() as db:
        stored = await db.get(Rfq, uuid.UUID(rfq["id"]))
        assert stored.expires_at - stored.submitted_at == timedelta(days=21)
        row = (await db.scalars(select(AdminAction).where(AdminAction.action == "trade_setting.update"))).one()
        assert row.details == {"from": "14.0000", "to": "21"}


async def test_rfq_text_may_not_name_the_buyer(client):
    await _buyer(client)  # legal name "Acme Agro 3 Pvt Ltd"
    rfq = (await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "1121 Basmati"})).json()
    r = await client.patch(f"/rfqs/{rfq['id']}", json={"notes": "Deliver to the Acme Agro warehouse"})
    assert r.status_code == 400 and "company name" in r.json()["detail"]
    r = await client.patch(f"/rfqs/{rfq['id']}", json={"notes": "Deliver to our warehouse at Jebel Ali"})
    assert r.status_code == 200


async def test_capacity_counts_the_months_left_and_incoterms_and_documents_must_fit(client, make_client, admin_client):
    # 2000 MT a month and 500 MT in stock; the buyer wants 3000 MT within five months.
    _, pid = await _seller(client, admin_client)
    buyer = make_client()
    await _buyer(buyer)
    long_window = {"quantity": "3000", "deliveryTo": (TODAY + timedelta(days=150)).isoformat()}
    rfq = await _submitted(buyer, **long_window)
    (match,) = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()["matches"]
    assert match["reasons"][1]["ok"] and "over 5 months" in match["reasons"][1]["detail"]

    # The listing offers FOB and CIF; a DAP-only buyer gets no proposal.
    dap = await _submitted(buyer, incoterms=["DAP"])
    assert (await admin_client.get(f"/admin/rfqs/{dap['id']}")).json()["matches"] == []
    r = await admin_client.post(f"/admin/rfqs/{dap['id']}/matches", json={"listingId": pid})
    assert r.status_code == 409 and "Buyer accepts DAP; listing offers FOB, CIF." in r.json()["detail"]

    # A requested document the listing doesn't carry rules it out.
    # The listing carries Rice's required COA but no product certificate.
    pc = next(t["id"] for t in (await _template(buyer))["certificateTypes"] if t["code"] == "product_certificate")
    needs_pc = await _submitted(buyer, certificateTypeIds=[pc])
    assert (await admin_client.get(f"/admin/rfqs/{needs_pc['id']}")).json()["matches"] == []
    r = await admin_client.post(f"/admin/rfqs/{needs_pc['id']}/matches", json={"listingId": pid})
    assert r.status_code == 409 and "Not on the listing: Product certificate." in r.json()["detail"]
