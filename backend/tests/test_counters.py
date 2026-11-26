"""Counter-offers (M4 · S8, CX-101, A-078): each side proposes in its own
currency, the desk sees what it means for the other side (back-solved
through the cost sheet), passes it on or refuses it, and the other side
answers. Neither side sees the other's own price."""
from __future__ import annotations

from decimal import Decimal

from conftest import set_status, signup_and_login
from sqlalchemy import select
from test_admin_accounts import _new_admin
from test_negotiation import _negotiating
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.models import AdminAction, BusinessStatus, CostSheet
from app.modules.negotiation import counters

# The quote fixture: ₹72,000.00 per MT (7,200,000 minor), other costs ₹5,000.00,
# both parties in India (INR, rate 1, no buffer), margin 8 %:
# selling price = (7,200,000 + 500,000) × 1.08 = 8,316,000.


async def test_a_buyer_counter_reaches_the_seller_as_a_seller_price(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    r = await p["buyer_client"].post(f"/deals/{code}/counters", json={"priceMinor": 8_000_000, "note": "For 500 MT."})
    assert r.status_code == 201, r.text
    mine = r.json()
    assert (mine["mine"], mine["priceMinor"], mine["currency"], mine["status"]) == (True, 8_000_000, "INR", "pending_desk")
    # Not passed on yet: the seller sees nothing.
    assert (await p["seller_client"].get(f"/deals/{code}/counters")).json()["items"] == []

    pending = (await admin_client.get("/admin/counters/pending")).json()["items"]
    # 8,000,000 / 1.08 = 7,407,407 (down), less 500,000 of costs.
    assert (pending[0]["impliedMinor"], pending[0]["impliedCurrency"]) == (6_907_407, "INR")
    r = await admin_client.post(f"/admin/counters/{pending[0]['id']}/relay", json={})
    assert r.status_code == 200 and r.json()["status"] == "relayed"

    theirs = (await p["seller_client"].get(f"/deals/{code}/counters")).json()["items"][0]
    assert (theirs["mine"], theirs["priceMinor"], theirs["status"]) == (False, 6_907_407, "relayed")
    assert "8000000" not in str(theirs) and "8,000,000" not in str(theirs)

    r = await p["seller_client"].post(f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": True})
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert (await p["buyer_client"].get(f"/deals/{code}/counters")).json()["items"][0]["status"] == "accepted"
    # Answered once; the buyer can't answer their own.
    assert (await p["seller_client"].post(f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": False})).status_code == 409
    assert (await p["buyer_client"].post(f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": True})).status_code == 404


async def test_a_seller_counter_reaches_the_buyer_as_a_selling_price(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["seller_client"].post(f"/deals/{code}/counters", json={"priceMinor": 7_000_000})
    pending = (await admin_client.get("/admin/counters/pending")).json()["items"][0]
    assert pending["impliedMinor"] == 8_100_000  # (7,000,000 + 500,000) × 1.08
    await admin_client.post(f"/admin/counters/{pending['id']}/relay", json={})
    theirs = (await p["buyer_client"].get(f"/deals/{code}/counters")).json()["items"][0]
    assert (theirs["priceMinor"], theirs["currency"]) == (8_100_000, "INR")
    r = await p["buyer_client"].post(f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": False})
    assert r.json()["status"] == "declined"


async def test_another_margin_outside_the_limits_needs_a_desk_manager(parties, admin_client, make_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["buyer_client"].post(f"/deals/{code}/counters", json={"priceMinor": 8_000_000})
    cid = (await admin_client.get("/admin/counters/pending")).json()["items"][0]["id"]
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    r = await desk.post(f"/admin/counters/{cid}/relay", json={"marginPct": "3"})
    assert r.status_code == 403 and "desk manager" in r.json()["detail"]
    # Within the limits the desk may change it.
    r = await desk.post(f"/admin/counters/{cid}/relay", json={"marginPct": "6"})
    assert r.status_code == 200
    body = r.json()
    assert (Decimal(body["marginPct"]), body["impliedMinor"]) == (Decimal("6"), 7_547_169 - 500_000)  # 8,000,000 / 1.06 = 7,547,169 (down)
    async with SessionLocal() as db:
        row = await db.scalar(select(AdminAction).where(AdminAction.action == "counter.relayed"))
    assert row.details["marginPct"] == "6.00"


async def test_a_refused_counter_tells_only_its_maker_why(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["seller_client"].post(f"/deals/{code}/counters", json={"priceMinor": 9_000_000})
    cid = (await admin_client.get("/admin/counters/pending")).json()["items"][0]["id"]
    assert (await admin_client.post(f"/admin/counters/{cid}/reject", json={"reason": "x"})).status_code == 422
    r = await admin_client.post(f"/admin/counters/{cid}/reject", json={"reason": "Above the market by a long way."})
    assert r.status_code == 200
    mine = (await p["seller_client"].get(f"/deals/{code}/counters")).json()["items"][0]
    assert (mine["status"], mine["decisionNote"]) == ("rejected", "Above the market by a long way.")
    assert (await p["buyer_client"].get(f"/deals/{code}/counters")).json()["items"] == []
    assert (await admin_client.post(f"/admin/counters/{cid}/relay", json={})).status_code == 409


async def test_a_new_counter_replaces_the_open_one(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["buyer_client"].post(f"/deals/{code}/counters", json={"priceMinor": 7_900_000})
    await p["buyer_client"].post(f"/deals/{code}/counters", json={"priceMinor": 8_050_000})
    mine = (await p["buyer_client"].get(f"/deals/{code}/counters")).json()["items"]
    assert [(c["priceMinor"], c["status"]) for c in mine] == [(8_050_000, "pending_desk"), (7_900_000, "superseded")]
    assert len((await admin_client.get("/admin/counters/pending")).json()["items"]) == 1


async def test_refusals(parties, admin_client, make_client):
    p = parties
    code = await _negotiating(p, admin_client)
    url = f"/deals/{code}/counters"
    r = await p["buyer_client"].post(url, json={"priceMinor": 400_000})
    assert r.status_code == 400 and "doesn't cover" in r.json()["detail"]
    r = await p["buyer_client"].post(url, json={"priceMinor": 8_000_000, "note": "Call 98765 43210"})
    assert r.status_code == 400 and "phone number" in r.json()["detail"]
    assert (await p["buyer_client"].post(url, json={"priceMinor": 0})).status_code == 422
    stranger = make_client()
    me = await signup_and_login(stranger, "nosy@othermill.in")
    await set_status(me["userId"], BusinessStatus.verified)
    assert (await stranger.get(url)).status_code == 404
    assert (await stranger.post(url, json={"priceMinor": 8_000_000})).status_code == 404
    _, reviewer = await _new_admin(admin_client, make_client, role="reviewer", email="rev2@cor1x.test")
    assert (await reviewer.get("/admin/counters/pending")).status_code == 403


async def test_the_back_solve_rounds_in_corridors_favour():
    sheet = CostSheet(
        purchase_currency="INR", purchase_price_minor=7_200_000, inland_freight_minor=150_000, ocean_freight_minor=250_000,
        insurance_minor=20_000, inspection_minor=30_000, documentation_minor=10_000, finance_minor=40_000, other_minor=0,
        deal_currency="USD", fx_rate=Decimal("0.01078600"), fx_buffer_pct=Decimal("2"), margin_pct=Decimal("8"),
    )
    for buyer in (90_000, 95_123, 101_777, 250_000):
        seller = counters.seller_price_for(buyer, sheet, sheet.margin_pct)
        # Passing the implied seller price back never asks the buyer for more than they offered.
        assert counters.buyer_price_for(seller, sheet, sheet.margin_pct) <= buyer
        # One minor unit more for the seller would.
        assert counters.buyer_price_for(seller + 1, sheet, sheet.margin_pct) > buyer
