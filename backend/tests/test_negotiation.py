"""Negotiation (M4 · S8, CX-099, CX-100, A-074, A-075): the buyer chooses an
offer, each side talks to the desk in its own thread, the leak filter stands
between them, and three blocked messages suspend a company."""
from __future__ import annotations

import uuid
from datetime import timedelta

from conftest import sent_emails, set_status, signup_and_login
from sqlalchemy import select, update
from test_admin_accounts import _new_admin
from test_quotes import SHEET, _credit, _quoted, parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models import AdminAction, Business, BusinessStatus, CostSheet, Deal, LeakStrike, Offer, Quote, RfqMatch


async def _offered(p, admin_client) -> tuple[dict, dict]:
    """An offer published to the buyer and unlocked by them."""
    rfq, quote = await _quoted(p["seller_client"], p["buyer_client"], admin_client, p["seller"])
    sheet = (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).json()
    offer = (await admin_client.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})).json()
    await _credit(p["buyer"]["businessId"])
    assert (await p["buyer_client"].post(f"/offers/{offer['id']}/unlock")).status_code == 200
    return rfq, offer


async def _negotiating(p, admin_client) -> str:
    rfq, offer = await _offered(p, admin_client)
    r = await p["buyer_client"].post(f"/deals/{rfq['dealCode']}/choose", json={"offerId": offer["id"]})
    assert r.status_code == 200, r.text
    return rfq["dealCode"]


# ── Choosing an offer ────────────────────────────────────────────────


async def test_choosing_an_offer_opens_negotiation_with_that_seller(parties, admin_client):
    p = parties
    rfq, offer = await _offered(p, admin_client)
    code = rfq["dealCode"]
    # Only the buyer, and only an offer of this deal.
    assert (await p["seller_client"].post(f"/deals/{code}/choose", json={"offerId": offer["id"]})).status_code == 404
    r = await p["buyer_client"].post(f"/deals/{code}/choose", json={"offerId": str(uuid.uuid4())})
    assert r.status_code == 404
    # Neither side can read a chat before an offer is chosen.
    assert (await p["buyer_client"].get(f"/deals/{code}/chat")).status_code == 404

    r = await p["buyer_client"].post(f"/deals/{code}/choose", json={"offerId": offer["id"]})
    assert r.status_code == 200 and r.json() == {"dealCode": code, "dealStatus": "NEGOTIATING", "chosenOfferId": offer["id"]}
    assert (await p["buyer_client"].post(f"/deals/{code}/choose", json={"offerId": offer["id"]})).status_code == 409
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
    assert str(deal.seller_business_id) == p["seller"]["businessId"] and str(deal.chosen_offer_id) == offer["id"]
    assert any("chose your offer" in m.subject for m in sent_emails())

    buyer = (await p["buyer_client"].get(f"/deals/{code}/chat")).json()
    seller = (await p["seller_client"].get(f"/deals/{code}/chat")).json()
    assert (buyer["side"], seller["side"]) == ("buyer", "seller")
    assert buyer["canWrite"] and [m["author"] for m in buyer["messages"]] == ["system"]
    seller_code = (await p["seller_client"].get("/me")).json()["companyCode"]
    assert buyer["counterpartyCode"] == seller_code


async def test_an_offer_must_be_unlocked_before_it_is_chosen(parties, admin_client):
    p = parties
    rfq, quote = await _quoted(p["seller_client"], p["buyer_client"], admin_client, p["seller"])
    sheet = (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).json()
    offer = (await admin_client.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})).json()
    r = await p["buyer_client"].post(f"/deals/{rfq['dealCode']}/choose", json={"offerId": offer["id"]})
    assert r.status_code == 400 and "Open the offer's price" in r.json()["detail"]


async def _second_offer(offer_id: str) -> uuid.UUID:
    """Another seller's live offer on the same deal: a copy of the first
    offer's match, quote, cost sheet and offer under a new business."""
    def copy(row, **over):
        values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        values.update(id=uuid.uuid4(), **over)
        return type(row)(**values)

    async with SessionLocal() as db:
        offer = await db.get(Offer, uuid.UUID(offer_id))
        sheet = await db.get(CostSheet, offer.cost_sheet_id)
        quote = await db.get(Quote, offer.quote_id)
        match = await db.get(RfqMatch, quote.match_id)
        other = Business(id=uuid.uuid4(), country="IN")
        db.add(other)
        await db.flush()
        m2 = copy(match, seller_business_id=other.id)
        db.add(m2)
        await db.flush()
        q2 = copy(quote, match_id=m2.id, seller_business_id=other.id)
        db.add(q2)
        await db.flush()
        s2 = copy(sheet, quote_id=q2.id)
        db.add(s2)
        await db.flush()
        o2 = copy(offer, quote_id=q2.id, cost_sheet_id=s2.id, seller_business_id=other.id)
        db.add(o2)
        await db.commit()
        return o2.id


async def test_the_other_offers_close_as_not_chosen(parties, admin_client):
    p = parties
    rfq, offer = await _offered(p, admin_client)
    second = await _second_offer(offer["id"])
    await p["buyer_client"].post(f"/deals/{rfq['dealCode']}/choose", json={"offerId": offer["id"]})
    async with SessionLocal() as db:
        assert (await db.get(Offer, second)).status == "not_chosen"
        assert (await db.get(Offer, uuid.UUID(offer["id"]))).status == "published"
    # The buyer's list no longer offers a choice.
    listed = (await p["buyer_client"].get(f"/rfqs/{rfq['id']}/offers")).json()["items"]
    assert {o["status"] for o in listed} == {"published", "not_chosen"}


# ── Messages ─────────────────────────────────────────────────────────


async def test_a_clean_message_reaches_the_other_side_by_company_code(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    r = await p["buyer_client"].post(f"/deals/{code}/chat", json={"body": "Can you hold the March shipment window?"})
    assert r.status_code == 201 and (r.json()["author"], r.json()["status"]) == ("you", "delivered")

    seller = (await p["seller_client"].get(f"/deals/{code}/chat")).json()["messages"]
    relay = seller[-1]
    buyer_code = (await p["buyer_client"].get("/me")).json()["companyCode"]
    assert (relay["author"], relay["senderCode"], relay["body"]) == ("counterparty", buyer_code, "Can you hold the March shipment window?")
    # The buyer's thread shows only their own line, not a copy back.
    assert [m["author"] for m in (await p["buyer_client"].get(f"/deals/{code}/chat")).json()["messages"]] == ["system", "you"]
    assert any(m.subject == f"New message on {code}" for m in sent_emails())
    assert "March" not in str([m.text for m in sent_emails() if m.subject == f"New message on {code}"])


async def test_contact_details_are_refused_and_three_strikes_suspend(parties, admin_client, make_client):
    p = parties
    code = await _negotiating(p, admin_client)
    url = f"/deals/{code}/chat"
    for attempt in ("Call me on 98765 43210", "Mail sales@kaveri.in", "WhatsApp nine eight seven six five four three two one zero"):
        r = await p["seller_client"].post(url, json={"body": attempt})
        assert r.status_code == 400 and r.json()["detail"].startswith("Not sent"), attempt
    # Nothing blocked reached the buyer or was stored.
    assert [m["author"] for m in (await p["buyer_client"].get(url)).json()["messages"]] == ["system"]
    async with SessionLocal() as db:
        assert len(list(await db.scalars(select(LeakStrike)))) == 3
        seller = await db.get(Business, uuid.UUID(p["seller"]["businessId"]))
    assert seller.suspended_at is not None

    # Suspended: reading works, writing does not.
    chat = (await p["seller_client"].get(url)).json()
    assert chat["suspended"] and not chat["canWrite"]
    r = await p["seller_client"].post(url, json={"body": "Fine, March works."})
    assert r.status_code == 403 and "can't trade" in r.json()["detail"]

    # Only a desk manager lifts it, with a reason.
    lift = f"/admin/businesses/{p['seller']['businessId']}/lift-suspension"
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    assert (await desk.post(lift, json={"reason": "Spoke to the seller about the rules."})).status_code == 403
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    assert (await manager.post(lift, json={"reason": "x"})).status_code == 422
    assert (await manager.post(lift, json={"reason": "Spoke to the seller about the rules."})).status_code == 204
    assert (await p["seller_client"].post(url, json={"body": "Fine, March works."})).status_code == 201


async def test_old_strikes_do_not_count(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    url = f"/deals/{code}/chat"
    for _ in range(2):
        await p["seller_client"].post(url, json={"body": "Call 98765 43210"})
    async with SessionLocal() as db:
        await db.execute(update(LeakStrike).values(created_at=utcnow() - timedelta(days=91)))
        await db.commit()
    await p["seller_client"].post(url, json={"body": "Call 98765 43210"})
    async with SessionLocal() as db:
        assert (await db.get(Business, uuid.UUID(p["seller"]["businessId"]))).suspended_at is None


async def test_a_doubtful_message_waits_for_the_desk(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    url = f"/deals/{code}/chat"
    r = await p["seller_client"].post(url, json={"body": "We supply Ganesh Traders Pvt Ltd every season."})
    assert r.status_code == 201 and r.json()["status"] == "held"
    assert [m["author"] for m in (await p["buyer_client"].get(url)).json()["messages"]] == ["system"]
    held = (await admin_client.get("/admin/chat/held")).json()["items"]
    assert held[0]["dealCode"] == code and held[0]["flags"]
    r = await admin_client.post(f"/admin/chat/{held[0]['id']}/reject", json={"reason": "This names your company."})
    assert r.status_code == 200
    mine = (await p["seller_client"].get(url)).json()["messages"][-1]
    assert (mine["status"], mine["note"]) == ("rejected", "This names your company.")
    assert (await admin_client.post(f"/admin/chat/{held[0]['id']}/release")).status_code == 409

    # Released instead, a held message reaches the other side.
    await p["seller_client"].post(url, json={"body": "We supply Ganesh Traders Pvt Ltd every season."})
    held = (await admin_client.get("/admin/chat/held")).json()["items"]
    assert (await admin_client.post(f"/admin/chat/{held[0]['id']}/release")).status_code == 200
    assert (await p["buyer_client"].get(url)).json()["messages"][-1]["author"] == "counterparty"


async def test_the_desk_reads_both_threads_and_writes_into_one(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["buyer_client"].post(f"/deals/{code}/chat", json={"body": "Is 820 possible?"})
    r = await admin_client.post(f"/admin/deals/{code}/chat/seller", json={"body": "The buyer asks about price; a counter-offer will follow."})
    assert r.status_code == 201
    threads = {t["side"]: t for t in r.json()["threads"]}
    assert [m["origin"] for m in threads["buyer"]["messages"]] == ["system", "own"]
    assert [m["origin"] for m in threads["seller"]["messages"]] == ["system", "relay", "desk"]
    seller_view = (await p["seller_client"].get(f"/deals/{code}/chat")).json()["messages"]
    assert seller_view[-1]["author"] == "corridor"
    async with SessionLocal() as db:
        assert await db.scalar(select(AdminAction).where(AdminAction.action == "chat.desk_message"))
    # A stranger sees nothing, and the trade desk route needs the permission.
    assert (await admin_client.post(f"/admin/deals/{code}/chat/nobody", json={"body": "x"})).status_code == 404


async def test_strangers_and_suspended_companies(parties, admin_client, make_client):
    p = parties
    code = await _negotiating(p, admin_client)
    stranger = make_client()
    me = await signup_and_login(stranger, "nosy@othermill.in")
    await set_status(me["userId"], BusinessStatus.verified)
    assert (await stranger.get(f"/deals/{code}/chat")).status_code == 404
    assert (await stranger.post(f"/deals/{code}/chat", json={"body": "hello"})).status_code == 404
    assert (await make_client().get(f"/deals/{code}/chat")).status_code == 401
    # A suspended buyer can't submit a new request.
    async with SessionLocal() as db:
        await db.execute(update(Business).where(Business.id == uuid.UUID(p["buyer"]["businessId"]))
                         .values(suspended_at=utcnow(), suspended_reason="test"))
        await db.commit()
    draft = (await p["buyer_client"].post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "Basmati"})).json()
    r = await p["buyer_client"].post(f"/rfqs/{draft['id']}/submit")
    assert r.status_code == 403 and "can't trade" in r.json()["detail"]


async def test_messages_and_chat_never_carry_a_name(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["buyer_client"].post(f"/deals/{code}/chat", json={"body": "Hello"})
    for c in (p["buyer_client"], p["seller_client"]):
        body = str((await c.get(f"/deals/{code}/chat")).json())
        assert "kaverifoods" not in body.lower() and "Kaveri" not in body
