"""Term sheets (M4 · S8, CX-103, A-076, A-079): the desk drafts each version,
issuing freezes and hashes it, each side reads only its own price and
accepts by hash, and both accepting makes it agreed. A later agreed version
supersedes the earlier one. The database refuses any change to issued terms."""
from __future__ import annotations

import uuid

import pytest
from conftest import sent_emails
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_admin_accounts import _new_admin
from test_negotiation import _negotiating
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.models import AdminAction, TermSheet

# The quote fixture: seller ₹72,000.00 per MT, other costs ₹5,000.00, both in
# INR at rate 1 with no buffer, margin 8 %: the buyer's price is ₹83,160.00.


async def _issued(p, admin_client, **changes) -> tuple[str, dict]:
    code = await _negotiating(p, admin_client)
    draft = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    if changes:
        draft = (await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json=changes)).json()
    r = await admin_client.post(f"/admin/term-sheets/{draft['id']}/issue")
    assert r.status_code == 200, r.text
    return code, r.json()


async def test_a_version_is_drafted_issued_and_agreed_by_both(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/term-sheets")
    assert r.status_code == 201, r.text
    draft = r.json()
    assert (draft["version"], draft["status"]) == (1, "draft")
    assert (draft["buyerPriceMinor"], draft["sellerPriceMinor"], draft["marginPct"]) == (8_316_000, 7_200_000, "8.00")
    # The buyer's specification limits, by name.
    assert draft["quality"] and "None" not in draft["quality"] and "at most" in draft["quality"]
    # One version at a time.
    assert (await admin_client.post(f"/admin/deals/{code}/term-sheets")).status_code == 409
    # A draft is the desk's: the traders see nothing yet.
    assert (await p["buyer_client"].get(f"/deals/{code}/term-sheets")).json()["items"] == []

    r = await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={
        "quantity": "400", "deliveryFrom": "2027-02-01", "deliveryTo": "2027-03-15",
        "notes": "Pre-shipment inspection by SGS at the port of loading.",
    })
    assert r.status_code == 200 and r.json()["quantity"] == "400.00"
    assert (await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"product": None})).status_code == 400
    r = await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"deliveryTo": "2027-01-01"})
    assert r.status_code == 400

    r = await admin_client.post(f"/admin/term-sheets/{draft['id']}/issue")
    assert r.status_code == 200 and r.json()["status"] == "issued"
    sha = r.json()["contentSha256"]
    assert len(sha) == 64
    assert sum("term sheet" in m.subject for m in sent_emails()) == 2
    # Issued terms are frozen.
    r = await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"quantity": "500"})
    assert r.status_code == 409

    buyer = (await p["buyer_client"].get(f"/deals/{code}/term-sheets")).json()["items"][0]
    seller = (await p["seller_client"].get(f"/deals/{code}/term-sheets")).json()["items"][0]
    assert (buyer["priceMinor"], buyer["currency"]) == (8_316_000, "INR")
    assert (seller["priceMinor"], seller["currency"]) == (7_200_000, "INR")
    # Neither side sees the other's price or the margin.
    assert "7200000" not in str(buyer) and "8316000" not in str(seller) and "margin" not in str(buyer).lower()
    assert buyer["contentSha256"] == seller["contentSha256"] == sha

    url = f"/deals/{code}/term-sheets/1"
    r = await p["buyer_client"].post(f"{url}/accept", json={"contentSha256": "0" * 64})
    assert r.status_code == 409 and "Reload it" in r.json()["detail"]
    r = await p["buyer_client"].post(f"{url}/accept", json={"contentSha256": sha})
    assert r.status_code == 200 and (r.json()["status"], r.json()["youAccepted"]) == ("issued", True)
    # Accepting twice changes nothing.
    assert (await p["buyer_client"].post(f"{url}/accept", json={"contentSha256": sha})).json()["status"] == "issued"
    assert (await p["seller_client"].get(f"/deals/{code}/term-sheets")).json()["items"][0]["otherAccepted"] is True

    r = await p["seller_client"].post(f"{url}/accept", json={"contentSha256": sha})
    assert r.status_code == 200 and r.json()["status"] == "agreed" and r.json()["agreedAt"]
    assert sum("is agreed" in m.subject for m in sent_emails()) == 2
    async with SessionLocal() as db:
        actions = set(await db.scalars(select(AdminAction.action).where(AdminAction.action.like("term_sheet.%"))))
    assert actions == {"term_sheet.drafted", "term_sheet.issued"}


async def test_the_database_refuses_a_change_to_issued_terms(parties, admin_client):
    p = parties
    _, issued = await _issued(p, admin_client)
    async with SessionLocal() as db:
        with pytest.raises((IntegrityError, DBAPIError)):
            await db.execute(
                update(TermSheet).where(TermSheet.id == uuid.UUID(issued["id"])).values(buyer_price_minor=1)
            )
            await db.flush()
        await db.rollback()
    async with SessionLocal() as db:
        # Status and acceptance can still move; the terms can't.
        await db.execute(update(TermSheet).where(TermSheet.id == uuid.UUID(issued["id"])).values(
            status="withdrawn", withdraw_note="Test of the trigger's scope."
        ))
        await db.commit()


async def test_a_later_agreed_version_supersedes_the_earlier(parties, admin_client):
    p = parties
    code, v1 = await _issued(p, admin_client)
    for c in (p["buyer_client"], p["seller_client"]):
        await c.post(f"/deals/{code}/term-sheets/1/accept", json={"contentSha256": v1["contentSha256"]})

    v2 = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    assert (v2["version"], v2["quantity"], v2["buyerPriceMinor"]) == (2, v1["quantity"], v1["buyerPriceMinor"])
    v2 = (await admin_client.patch(f"/admin/term-sheets/{v2['id']}", json={"quantity": "250"})).json()
    v2 = (await admin_client.post(f"/admin/term-sheets/{v2['id']}/issue")).json()
    assert v2["contentSha256"] != v1["contentSha256"]
    # The old hash doesn't accept the new version.
    r = await p["buyer_client"].post(f"/deals/{code}/term-sheets/2/accept", json={"contentSha256": v1["contentSha256"]})
    assert r.status_code == 409
    for c in (p["buyer_client"], p["seller_client"]):
        await c.post(f"/deals/{code}/term-sheets/2/accept", json={"contentSha256": v2["contentSha256"]})

    rows = (await admin_client.get(f"/admin/deals/{code}/term-sheets")).json()["items"]
    assert [(r["version"], r["status"]) for r in rows] == [(2, "agreed"), (1, "superseded")]
    assert rows[1]["supersededAt"]


async def test_a_side_declines_with_a_reason_and_the_desk_withdraws(parties, admin_client):
    p = parties
    code, v1 = await _issued(p, admin_client)
    url = f"/deals/{code}/term-sheets/1/decline"
    r = await p["seller_client"].post(url, json={"reason": "Call me on +91 98450 11001 to discuss."})
    assert r.status_code == 400
    r = await p["seller_client"].post(url, json={"reason": "The delivery window is too short for this quantity."})
    assert r.status_code == 200 and r.json()["status"] == "declined" and r.json()["declineNote"]
    # The buyer sees it was declined, not the seller's reason.
    buyer = (await p["buyer_client"].get(f"/deals/{code}/term-sheets")).json()["items"][0]
    assert buyer["status"] == "declined" and buyer["declineNote"] is None
    r = await p["buyer_client"].post(f"/deals/{code}/term-sheets/1/accept", json={"contentSha256": v1["contentSha256"]})
    assert r.status_code == 409

    v2 = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    r = await admin_client.post(f"/admin/term-sheets/{v2['id']}/withdraw", json={"reason": "Waiting for a new freight quote."})
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert (await admin_client.post(f"/admin/term-sheets/{v2['id']}/issue")).status_code == 409


async def test_a_margin_outside_the_limits_needs_a_desk_manager(parties, admin_client, make_client):
    p = parties
    code = await _negotiating(p, admin_client)
    draft = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    # ₹78,000.00 against ₹77,000.00 of cost is about 1.3 %, under the floor.
    await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"buyerPriceMinor": 7_800_000})
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    r = await desk.post(f"/admin/term-sheets/{draft['id']}/issue")
    assert r.status_code == 403 and "desk manager" in r.json()["detail"]
    # Below cost is refused for everyone.
    await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"buyerPriceMinor": 7_000_000})
    assert (await admin_client.post(f"/admin/term-sheets/{draft['id']}/issue")).status_code == 400
    await admin_client.patch(f"/admin/term-sheets/{draft['id']}", json={"buyerPriceMinor": 7_800_000})
    assert (await admin_client.post(f"/admin/term-sheets/{draft['id']}/issue")).status_code == 200


async def test_the_first_version_takes_the_accepted_counter_offer(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    await p["buyer_client"].post(f"/deals/{code}/counters", json={"priceMinor": 8_000_000, "quantity": "450"})
    cid = (await admin_client.get("/admin/counters/pending")).json()["items"][0]["id"]
    await admin_client.post(f"/admin/counters/{cid}/relay", json={})
    theirs = (await p["seller_client"].get(f"/deals/{code}/counters")).json()["items"][0]
    await p["seller_client"].post(f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": True})
    draft = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    # 8,000,000 / 1.08 = 7,407,407 (down), less 500,000 of costs.
    assert (draft["buyerPriceMinor"], draft["sellerPriceMinor"], draft["quantity"]) == (8_000_000, 6_907_407, "450.00")


async def test_outsiders_see_nothing(parties, admin_client, make_client):
    p = parties
    code, v1 = await _issued(p, admin_client)
    assert (await make_client().get(f"/deals/{code}/term-sheets")).status_code == 401
    _, reviewer = await _new_admin(admin_client, make_client, role="reviewer", email="rev@cor1x.test")
    assert (await reviewer.get(f"/admin/deals/{code}/term-sheets")).status_code == 403
    assert (await reviewer.post(f"/admin/term-sheets/{v1['id']}/issue")).status_code == 403
    # A version that doesn't exist, or a draft, is 404 to a trader.
    r = await p["buyer_client"].post(f"/deals/{code}/term-sheets/9/accept", json={"contentSha256": v1["contentSha256"]})
    assert r.status_code == 404
