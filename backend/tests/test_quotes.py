"""Quote → cost sheet → offer → unlock (CX-095, CX-096, CX-097): what a
seller may quote, how the desk prices it, who approves a thin margin, and
that a buyer never sees what Corridor One X pays."""
from __future__ import annotations

import typing
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from test_admin_accounts import _new_admin
from test_rfq import _buyer, _seller, _submitted

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.main import app
from app.models import AdminAction, Business, CostSheet, Deal, DealEvent, ExchangeRate, Offer, Quote
from app.modules.credits import service as credits
from app.modules.quotes import service as quotes

TODAY = utcnow().date()


def _days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


async def _credit(business_id: str, amount: int = 20) -> None:
    async with SessionLocal() as db:
        await credits._post(db, uuid.UUID(business_id), "TOP_UP", amount, idempotency_key=f"test-{uuid.uuid4()}")
        await db.commit()


async def _opened(seller_client, buyer_client, admin_client, seller: dict) -> dict:
    """An RFQ submitted, confirmed by the desk and opened by the seller."""
    rfq = await _submitted(buyer_client)
    assert (await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")).status_code == 200
    await _credit(seller["businessId"])
    r = await seller_client.post(f"/matched-rfqs/{rfq['id']}/open")
    assert r.status_code == 200, r.text
    return {**rfq, "view": r.json()}


def _quote_body(view: dict, **over) -> dict:
    body = {
        "priceMinor": 7200000, "currency": "INR", "quantity": "500", "unit": "MT", "incoterm": "FOB",
        "portOfLoading": "Mundra", "leadTimeDays": 14, "paymentTerms": ["lc_sight", "advance"],
        "validUntil": _days(10), "notes": "Fresh 2026 crop.",
        "specs": [{"parameterId": s["parameterId"], "meets": True, "value": "5"} for s in view["specs"]],
    }
    body.update(over)
    return body


async def _quoted(seller_client, buyer_client, admin_client, seller, **over) -> tuple[dict, dict]:
    rfq = await _opened(seller_client, buyer_client, admin_client, seller)
    r = await seller_client.put(f"/matched-rfqs/{rfq['id']}/quote", json=_quote_body(rfq["view"], **over))
    assert r.status_code == 200, r.text
    return rfq, r.json()


SHEET = {
    "inlandFreightMinor": 150000, "oceanFreightMinor": 250000, "freightQuotedOn": TODAY.isoformat(),
    "insuranceMinor": 20000, "inspectionMinor": 30000, "documentationMinor": 10000, "financeMinor": 40000,
    "otherMinor": 0, "marginPct": "8",
}


@pytest.fixture
async def parties(client, make_client, admin_client):
    seller, listing = await _seller(client, admin_client)
    buyer_client = make_client()
    buyer = await _buyer(buyer_client)
    return {"seller": seller, "seller_client": client, "buyer": buyer, "buyer_client": buyer_client, "listing": listing}


# ── Seller quote ─────────────────────────────────────────────────────


async def test_a_quote_needs_the_request_opened_and_every_required_spec_answered(parties, admin_client, make_client):
    s, b = parties["seller_client"], parties["buyer_client"]
    rfq = await _submitted(b)
    await admin_client.post(f"/admin/rfqs/{rfq['id']}/confirm")
    url = f"/matched-rfqs/{rfq['id']}/quote"
    preview = (await b.get(f"/rfqs/{rfq['id']}/seller-preview")).json()

    r = await s.put(url, json=_quote_body(preview))
    assert r.status_code == 409 and r.json()["detail"] == "Open the request before quoting on it."
    await _credit(parties["seller"]["businessId"])
    view = (await s.post(f"/matched-rfqs/{rfq['id']}/open")).json()

    r = await s.put(url, json=_quote_body(view, specs=_quote_body(view)["specs"][1:]))
    assert r.status_code == 400 and r.json()["detail"].startswith("Say whether you meet each required specification.")
    r = await s.put(url, json=_quote_body(view, incoterm="CIF"))
    assert r.status_code == 400 and "FOB" in r.json()["detail"]
    r = await s.put(url, json=_quote_body(view, unit="kg"))
    assert r.status_code == 400
    r = await s.put(url, json=_quote_body(view, notes="call 98765 43210 for a better price"))
    assert r.status_code == 400 and "phone number" in r.json()["detail"]
    # The seller's own name (signed up as "seller kaverifoods Trading") is refused too (C25).
    r = await s.put(url, json=_quote_body(view, notes="Milled and packed by Seller Kaverifoods Trading"))
    assert r.status_code == 400 and "company name" in r.json()["detail"]
    r = await s.put(url, json=_quote_body(view, validUntil=_days(1)))
    assert r.status_code == 400 and "at least 2 more days" in r.json()["detail"]
    assert (await s.put(url, json=_quote_body(view, priceMinor=0))).status_code == 422
    assert (await s.get(url)).status_code == 404  # nothing was saved

    r = await s.put(url, json=_quote_body(view, validUntil=None))
    assert r.status_code == 200, r.text
    quote = r.json()
    assert quote["validUntil"] == _days(7) and quote["editable"] is True  # the 7-day default
    assert [a["name"] for a in quote["specs"]] and all(a["meets"] for a in quote["specs"])
    revised = (await s.put(url, json=_quote_body(view, priceMinor=7100000))).json()
    assert revised["id"] == quote["id"] and revised["priceMinor"] == 7100000  # one quote per seller per RFQ

    # The quote is the seller's: not the buyer's, not another seller's.
    stranger = make_client()
    await _seller(stranger, admin_client, "second@othermill.in", capacityPerMonth="100")
    for other in (b, stranger):
        assert (await other.get(url)).status_code == 404
        assert (await other.put(url, json=_quote_body(view))).status_code == 404
    assert (await b.get(f"/rfqs/{rfq['id']}/offers")).json() == {"total": 0, "items": []}


# ── Cost sheet ───────────────────────────────────────────────────────


async def test_cost_sheet_prices_the_quote_and_refuses_stale_freight(parties, admin_client):
    rfq, quote = await _quoted(parties["seller_client"], parties["buyer_client"], admin_client, parties["seller"])
    listed = (await admin_client.get(f"/admin/rfqs/{rfq['id']}/quotes")).json()["items"]
    assert len(listed) == 1 and listed[0]["costSheet"] is None and listed[0]["priceMinor"] == 7200000
    assert listed[0]["sellerCode"] and "kaverifoods" not in str(listed).lower()  # the desk sees a code
    url = f"/admin/quotes/{quote['id']}/cost-sheet"

    assert (await admin_client.put(url, json={**SHEET, "freightQuotedOn": None})).status_code == 400
    r = await admin_client.put(url, json={**SHEET, "freightQuotedOn": (TODAY - timedelta(days=8)).isoformat()})
    assert r.status_code == 400 and r.json()["detail"] == "That freight quote is more than 7 days old. Get a current one."
    assert (await admin_client.put(url, json={**SHEET, "freightQuotedOn": _days(1)})).status_code == 400
    assert (await admin_client.put(url, json={**SHEET, "marginPct": "-1"})).status_code == 422
    assert (await admin_client.put(f"/admin/quotes/{uuid.uuid4()}/cost-sheet", json=SHEET)).status_code == 404

    r = await admin_client.put(url, json={**SHEET, "freightQuotedOn": (TODAY - timedelta(days=7)).isoformat()})
    assert r.status_code == 200, r.text
    sheet = r.json()
    # Buyer and seller are both in India: no conversion, no buffer.
    assert (sheet["purchaseCurrency"], sheet["dealCurrency"], sheet["fxRate"], sheet["fxBufferPct"]) == (
        "INR", "INR", "1.00000000", "0.00",
    )
    assert sheet["totalCostMinor"] == 7200000 + 150000 + 250000 + 20000 + 30000 + 10000 + 40000 == 7700000
    assert sheet["sellPriceMinor"] == 8316000  # 7,700,000 × 1.08
    assert (sheet["status"], sheet["needsApproval"], sheet["minMarginPct"]) == ("ready", False, "5.00")

    # Once the desk is working on it the seller can no longer change the quote.
    s = parties["seller_client"]
    r = await s.put(f"/matched-rfqs/{rfq['id']}/quote", json=_quote_body(rfq["view"], priceMinor=1))
    assert r.status_code == 409 and "can no longer be changed" in r.json()["detail"]
    assert (await s.get(f"/matched-rfqs/{rfq['id']}/quote")).json()["editable"] is False


def test_sell_price_rounds_up_so_rounding_never_eats_the_margin():
    assert quotes.sell_price(7700000, Decimal(1), Decimal(0), Decimal(8)) == 8316000
    assert quotes.sell_price(100, Decimal("0.01204819"), Decimal(2), Decimal(5)) == 2  # 1.29 → 2, never 1
    assert quotes.sell_price(1, Decimal(1), Decimal(0), Decimal(0)) == 1


async def test_a_cross_border_sheet_stores_the_rate_and_buffer_it_was_priced_at(parties, admin_client):
    async with SessionLocal() as db:
        await db.execute(update(Business).where(Business.id == uuid.UUID(parties["buyer"]["businessId"])).values(country="AE"))
        db.add(ExchangeRate(base="USD", quote="INR", rate=Decimal("80"), as_of=TODAY, source="test", fetched_at=utcnow()))
        await db.commit()
    rfq, quote = await _quoted(parties["seller_client"], parties["buyer_client"], admin_client, parties["seller"])
    url = f"/admin/quotes/{quote['id']}/cost-sheet"
    sheet = (await admin_client.put(url, json=SHEET)).json()
    assert (sheet["dealCurrency"], sheet["fxRate"], sheet["fxAsOf"], sheet["fxBufferPct"]) == (
        "USD", "0.01250000", TODAY.isoformat(), "2.00",
    )
    # 7,700,000 paise ÷ 80 × 1.02 buffer × 1.08 margin = 106,029 cents
    assert sheet["sellPriceMinor"] == 106029
    offer = (await admin_client.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})).json()
    assert (offer["priceMinor"], offer["currency"]) == (106029, "USD")

    # The market moves. The sheet and the offer keep the rate they were priced at.
    async with SessionLocal() as db:
        await db.execute(update(ExchangeRate).values(rate=Decimal("95")))
        await db.commit()
    again = (await admin_client.get(f"/admin/rfqs/{rfq['id']}/quotes")).json()["items"][0]["costSheet"]
    assert (again["fxRate"], again["sellPriceMinor"]) == ("0.01250000", 106029)


async def test_no_rate_means_no_sheet(parties, admin_client):
    async with SessionLocal() as db:
        await db.execute(update(Business).where(Business.id == uuid.UUID(parties["buyer"]["businessId"])).values(country="AE"))
        await db.commit()
    rfq, quote = await _quoted(parties["seller_client"], parties["buyer_client"], admin_client, parties["seller"])
    r = await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)
    assert r.status_code == 409 and "no exchange rate for INR" in r.json()["detail"]


async def test_a_margin_under_the_floor_needs_a_manager_who_is_not_the_author(parties, admin_client, make_client):
    rfq, quote = await _quoted(parties["seller_client"], parties["buyer_client"], admin_client, parties["seller"])
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="manager@cor1x.test")
    _, second = await _new_admin(admin_client, make_client, role="desk_manager", email="second@cor1x.test")
    url = f"/admin/quotes/{quote['id']}/cost-sheet"

    sheet = (await manager.put(url, json={**SHEET, "marginPct": "3"})).json()  # the floor is 5
    assert (sheet["status"], sheet["needsApproval"], sheet["approved"]) == ("pending_approval", True, False)
    r = await manager.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})
    assert r.status_code == 409 and "desk manager's approval" in r.json()["detail"]
    assert (await desk.post(f"/admin/cost-sheets/{sheet['id']}/approve")).status_code == 403  # not a manager
    r = await manager.post(f"/admin/cost-sheets/{sheet['id']}/approve")
    assert r.status_code == 403 and "other than the sheet's author" in r.json()["detail"]

    r = await second.post(f"/admin/cost-sheets/{sheet['id']}/approve")
    assert r.status_code == 200 and (r.json()["status"], r.json()["approved"]) == ("ready", True)
    assert (await second.post(f"/admin/cost-sheets/{sheet['id']}/approve")).status_code == 409  # nothing to approve

    # Changing the numbers throws the approval away.
    again = (await desk.put(url, json={**SHEET, "marginPct": "2"})).json()
    assert (again["status"], again["approved"]) == ("pending_approval", False)
    assert (await desk.put(url, json={**SHEET, "marginPct": "5"})).json()["status"] == "ready"  # at the floor is fine

    async with SessionLocal() as db:
        row = await db.scalar(select(CostSheet))
        with pytest.raises(IntegrityError) as err:  # the database holds the rule too
            await db.execute(update(CostSheet).values(approved_by=row.created_by, approved_at=utcnow()))
        assert "ck_cost_sheets_second_approver" in str(err.value.orig)
    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).where(AdminAction.action.like("cost_sheet.%")).order_by(AdminAction.created_at))]
    assert actions == ["cost_sheet.save", "cost_sheet.approve", "cost_sheet.save", "cost_sheet.save"]


# ── Offer ────────────────────────────────────────────────────────────


async def test_publishing_moves_the_deal_to_quoted_and_the_offer_ends_before_the_quote(parties, admin_client):
    b = parties["buyer_client"]
    rfq, quote = await _quoted(parties["seller_client"], b, admin_client, parties["seller"])  # quote valid 10 days
    sheet = (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).json()
    url = f"/admin/cost-sheets/{sheet['id']}/publish"

    r = await admin_client.post(url, json={"validUntil": _days(9)})
    assert r.status_code == 400 and f"has to end by {_days(8)}" in r.json()["detail"]
    r = await admin_client.post(url, json={})
    assert r.status_code == 201, r.text
    offer = r.json()
    assert (offer["dealStatus"], offer["validUntil"], offer["dealCode"]) == ("QUOTED", _days(8), rfq["dealCode"])
    assert (await admin_client.post(url, json={})).status_code == 409  # one offer per sheet
    assert (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).status_code == 409

    assert (await b.get(f"/rfqs/{rfq['id']}")).json()["tracking"] == "quoted"
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal))
        events = [(e.from_status, e.to_status, e.action, e.actor_type) for e in await db.scalars(select(DealEvent).order_by(DealEvent.created_at))]
        assert deal.status == "QUOTED" and events == [
            (None, "RFQ_OPEN", "rfq_submitted", "user"), ("RFQ_OPEN", "QUOTED", "offer_published", "admin"),
        ]
        from app.modules.rfq import service as rfqs

        await db.execute(update(Offer).values(valid_until=TODAY - timedelta(days=1)))
        await db.execute(update(quotes.Rfq).values(expires_at=utcnow() - timedelta(days=1)))
        await db.commit()
        assert await rfqs.expire_due(db) == 0  # a quoted deal is not expired with its RFQ


async def test_a_buyer_sees_terms_for_free_and_the_price_after_unlocking_once(parties, admin_client, make_client):
    b, s = parties["buyer_client"], parties["seller_client"]
    rfq, quote = await _quoted(s, b, admin_client, parties["seller"])
    sheet = (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).json()
    offer_id = (await admin_client.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})).json()["id"]

    listed = (await b.get(f"/rfqs/{rfq['id']}/offers")).json()
    assert listed["total"] == 1
    locked = listed["items"][0]
    assert (locked["unlocked"], locked["unlockCost"], locked["incoterm"], locked["leadTimeDays"]) == (False, 2, "FOB", 14)
    assert (locked["specsMet"], locked["specsTotal"]) == (len(rfq["view"]["specs"]), len(rfq["view"]["specs"]))
    assert locked["sellerCode"] == (await s.get("/me")).json()["companyCode"]
    assert locked["priceMinor"] is None and locked["quantity"] is None and locked["paymentTerms"] is None
    assert "8316000" not in str(listed)  # the price is not hidden in some other field

    r = await b.post(f"/offers/{offer_id}/unlock")
    assert r.status_code == 402 and "This costs 2 credits and you have 0." in r.json()["detail"]
    await _credit(parties["buyer"]["businessId"], 5)
    r = await b.post(f"/offers/{offer_id}/unlock")
    assert r.status_code == 200, r.text
    opened = r.json()
    assert (opened["unlocked"], opened["unlockCost"], opened["priceMinor"], opened["currency"]) == (True, 0, 8316000, "INR")
    assert (opened["quantity"], opened["portOfLoading"], opened["paymentTerms"]) == ("500.00", "Mundra", ["lc_sight", "advance"])
    assert (await b.post(f"/offers/{offer_id}/unlock")).status_code == 200  # again: free
    assert (await b.get("/wallet")).json()["balance"] == 3
    assert (await b.get(f"/rfqs/{rfq['id']}/offers")).json()["items"][0]["priceMinor"] == 8316000

    # What Corridor One X pays never reaches the buyer, locked or unlocked.
    everything = str(listed) + str(opened) + str((await b.get(f"/rfqs/{rfq['id']}")).json())
    assert "7200000" not in everything and "7700000" not in everything
    assert parties["seller"]["businessId"] not in everything and "kaverifoods" not in everything.lower()

    # The offer is the buyer's alone.
    stranger = make_client()
    await _buyer(stranger, "second@othermill.in", n=4)
    for other in (stranger, s):
        assert (await other.post(f"/offers/{offer_id}/unlock")).status_code == 404
        assert (await other.get(f"/rfqs/{rfq['id']}/offers")).status_code == 404
    assert (await make_client().post(f"/offers/{offer_id}/unlock")).status_code == 401


async def test_an_expired_offer_cannot_be_unlocked(parties, admin_client):
    b = parties["buyer_client"]
    rfq, quote = await _quoted(parties["seller_client"], b, admin_client, parties["seller"])
    sheet = (await admin_client.put(f"/admin/quotes/{quote['id']}/cost-sheet", json=SHEET)).json()
    offer_id = (await admin_client.post(f"/admin/cost-sheets/{sheet['id']}/publish", json={})).json()["id"]
    await _credit(parties["buyer"]["businessId"], 5)
    async with SessionLocal() as db:
        await db.execute(update(Offer).values(valid_until=TODAY - timedelta(days=1)))
        await db.commit()
    assert (await b.get(f"/rfqs/{rfq['id']}/offers")).json()["items"][0]["status"] == "expired"
    r = await b.post(f"/offers/{offer_id}/unlock")
    assert r.status_code == 409 and r.json()["detail"] == "This offer has expired."
    assert (await b.get("/wallet")).json()["balance"] == 5  # nothing charged


# ── The purchase price cannot leave the desk ─────────────────────────

#: Field-name fragments that belong to the quote and the cost sheet.
DESK_ONLY = ("purchase", "margin", "cost", "fx_rate", "fx_buffer", "freight", "target_price")
#: Routes outside /admin whose response may carry one, and why.
ALLOWED = {
    ("GET", "/rfqs"): "the buyer's own target price",
    ("POST", "/rfqs"): "the buyer's own target price",
    ("GET", "/rfqs/{rfq_id}"): "the buyer's own target price",
    ("PATCH", "/rfqs/{rfq_id}"): "the buyer's own target price",
    ("POST", "/rfqs/{rfq_id}/submit"): "the buyer's own target price",
    ("GET", "/matched-rfqs"): "open_cost: the credits to open an RFQ",
    ("GET", "/rfqs/{rfq_id}/offers"): "unlock_cost: the credits to unlock an offer",
    ("POST", "/offers/{offer_id}/unlock"): "unlock_cost: the credits to unlock an offer",
}


def _fields(annotation, seen: set) -> set[str]:
    found: set[str] = set()
    for arg in typing.get_args(annotation):
        found |= _fields(arg, seen)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation not in seen:
        seen.add(annotation)
        for name, field in annotation.model_fields.items():
            found.add(name)
            found |= _fields(field.annotation, seen)
    return found


def test_no_external_response_model_can_carry_a_cost_or_the_purchase_price():
    leaks, checked = [], 0
    for ctx in iter_route_contexts(app.routes):
        route, path = ctx.original_route, ctx.path.removeprefix("/v1")
        if not isinstance(route, APIRoute) or path.startswith("/admin") or route.response_model is None:
            continue
        checked += 1
        bad = sorted(f for f in _fields(route.response_model, set()) if any(part in f for part in DESK_ONLY))
        for method in ctx.methods:
            allowed = ALLOWED.get((method, path))
            if bad and not allowed:
                leaks.append(f"{method} {path}: {bad}")
            if allowed and bad not in (["target_price_max", "target_price_min"], ["open_cost"], ["unlock_cost"]):
                leaks.append(f"{method} {path}: allowed for one field, carries {bad}")
    assert checked > 40 and not leaks, "\n".join(leaks)
    # The seller's view of an RFQ is the one place the buyer's price must not be.
    from app.modules.rfq.schemas import RfqSellerView

    assert not [f for f in RfqSellerView.model_fields if "price" in f]
