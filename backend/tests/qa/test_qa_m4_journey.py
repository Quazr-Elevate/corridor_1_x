"""M4 journey (S8 + S9): one deal from a chosen offer to two effective
contracts, the way the three people involved would walk it, with the
refusals each step must make on the way. Every response either trader
receives is kept and checked at the end: neither ever sees the other's
legal name, email or price.

    choose offer → chat (relayed, blocked, held then released) → counter-offer
    → sample → term sheet → LOIs → contracts (a pair that doesn't mirror is
    refused) → CONTRACTED
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from test_admin_accounts import _new_admin
from test_contracts import PURCHASE, REVIEWED, TERMS
from test_lois import SIGN, approve_templates
from test_negotiation import _offered
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.models import Deal, DealDocument, DealEvent, User
from app.modules.masking import service as masking


class Seen:
    """Every JSON body one trader was sent during the journey."""

    def __init__(self, client):
        self.client, self.bodies = client, []

    async def __call__(self, method: str, url: str, **kw):
        r = await getattr(self.client, method)(url, **kw)
        self.bodies.append(r.text)
        return r

    def text(self) -> str:
        return "\n".join(self.bodies)


async def _identity(user_id: str) -> tuple[str, str]:
    async with SessionLocal() as db:
        user = await db.get(User, uuid.UUID(user_id))
        party = await masking.party_for_document(db, user.business_id)
        contact = await masking.contact_of(db, user.id)
    return party.legal_name, contact.email


async def test_one_deal_from_offer_to_contracts(parties, admin_client, make_client):
    p = parties
    buyer, seller = Seen(p["buyer_client"]), Seen(p["seller_client"])
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")

    # ── Choose the offer ─────────────────────────────────────────────
    rfq, offer = await _offered(p, admin_client)
    code = rfq["dealCode"]
    r = await buyer("post", f"/deals/{code}/choose", json={"offerId": offer["id"]})
    assert r.status_code == 200 and r.json()["dealStatus"] == "NEGOTIATING"

    # ── Chat ─────────────────────────────────────────────────────────
    chat = f"/deals/{code}/chat"
    assert (await buyer("post", chat, json={"body": "Can you hold the March shipment window?"})).json()["status"] == "delivered"
    relayed = (await seller("get", chat)).json()["messages"]
    assert relayed[-1]["author"] == "counterparty" and "March" in relayed[-1]["body"]
    r = await seller("post", chat, json={"body": "Call me on 98765 43210"})
    assert r.status_code == 400  # blocked, a strike, never relayed
    r = await seller("post", chat, json={"body": "We supply Ganesh Traders Pvt Ltd every season."})
    assert r.json()["status"] == "held"
    held = (await admin_client.get("/admin/chat/held")).json()["items"][0]
    assert (await admin_client.post(f"/admin/chat/{held['id']}/release")).status_code == 200
    seen_by_buyer = [m["body"] for m in (await buyer("get", chat)).json()["messages"]]
    assert any("Ganesh" in b for b in seen_by_buyer) and not any("98765" in b for b in seen_by_buyer)

    # ── Counter-offer ────────────────────────────────────────────────
    r = await buyer("post", f"/deals/{code}/counters", json={"priceMinor": 8_000_000, "quantity": "450"})
    assert r.status_code == 201
    pending = (await admin_client.get("/admin/counters/pending")).json()["items"][0]
    assert (await admin_client.post(f"/admin/counters/{pending['id']}/relay", json={})).status_code == 200
    theirs = (await seller("get", f"/deals/{code}/counters")).json()["items"][0]
    assert theirs["priceMinor"] == 6_907_407  # what ₹80,000 means for the seller
    assert (await seller("post", f"/deals/{code}/counters/{theirs['id']}/answer", json={"accept": True})).json()["status"] == "accepted"

    # ── Sample ───────────────────────────────────────────────────────
    r = await buyer("post", f"/deals/{code}/samples")
    assert r.status_code == 201
    sid = r.json()["id"]
    assert (await seller("get", f"/deals/{code}/samples")).json()["items"][0]["hubAddress"]
    await seller("post", f"/deals/{code}/samples/{sid}/dispatch", json={"courierRef": "DTDC D1234567"})
    await admin_client.post(f"/admin/samples/{sid}/at-hub")
    assert (await admin_client.post(f"/admin/samples/{sid}/forward", json={"courierRef": "BLUEDART 99887766"})).status_code == 409
    await admin_client.post(f"/admin/samples/{sid}/seal", json={"retainedSealNo": "SEAL-0001", "forwardSealNo": "SEAL-0002"})
    await admin_client.post(f"/admin/samples/{sid}/forward", json={"courierRef": "BLUEDART 99887766"})
    await admin_client.post(f"/admin/samples/{sid}/received")
    r = await buyer("post", f"/deals/{code}/samples/{sid}/review", json={"verdict": "passed", "note": "Grain length 8.2 mm."})
    assert r.json()["status"] == "reviewed"

    # ── Term sheet: version 1 takes the accepted counter ─────────────
    draft = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    assert (draft["buyerPriceMinor"], draft["sellerPriceMinor"], draft["quantity"]) == (8_000_000, 6_907_407, "450.00")
    issued = (await admin_client.post(f"/admin/term-sheets/{draft['id']}/issue")).json()
    for side in (buyer, seller):
        r = await side("post", f"/deals/{code}/term-sheets/1/accept", json={"contentSha256": issued["contentSha256"]})
        assert r.status_code == 200
    assert r.json()["status"] == "agreed"

    # ── LOIs ─────────────────────────────────────────────────────────
    assert (await admin_client.post(f"/admin/deals/{code}/lois")).status_code == 409  # no lawyer yet
    await approve_templates(admin_client, codes=("loi_buy", "loi_sell", "sales", "purchase"))
    assert (await admin_client.post(f"/admin/deals/{code}/lois")).status_code == 201
    for side in (buyer, seller):
        d = (await side("get", f"/deals/{code}/documents")).json()["items"][0]
        assert (await side("post", f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})).status_code == 200
        assert (await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})).status_code == 200

    # ── Contracts ────────────────────────────────────────────────────
    url = f"/admin/deals/{code}/contracts"
    r = await admin_client.post(url, json={"sales": TERMS, "purchase": TERMS, "legalReviewNote": REVIEWED})
    assert r.status_code == 422 and r.json()["fields"][0]["field"] == "purchase.late_penalty_pct"
    assert (await admin_client.post(url, json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})).status_code == 201
    for side in (buyer, seller):
        d = [x for x in (await side("get", f"/deals/{code}/documents")).json()["items"] if x["kind"] == "contract"][0]
        await side("post", f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
        await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})

    # ── Where it ended ───────────────────────────────────────────────
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        path = [e.to_status for e in await db.scalars(
            select(DealEvent).where(DealEvent.deal_id == deal.id).order_by(DealEvent.created_at)
        )]
        effective = list(await db.scalars(select(DealDocument).where(DealDocument.status == "effective")))
    assert deal.status == "CONTRACTED"
    assert path == ["RFQ_OPEN", "QUOTED", "NEGOTIATING", "LOI_SIGNED", "CONTRACTED"]
    assert len(effective) == 2 and len({d.effective_at for d in effective}) == 1

    # Neither side was ever sent the other's identity or the other's price.
    buyer_name, buyer_email = await _identity(p["buyer"]["userId"])
    seller_name, seller_email = await _identity(p["seller"]["userId"])
    assert seller_name not in buyer.text() and seller_email not in buyer.text()
    assert buyer_name not in seller.text() and buyer_email not in seller.text()
    assert "6907407" not in buyer.text() and "8000000" not in seller.text().replace(" ", "")
    # Each received its own contract only.
    assert "SALES CONTRACT" in buyer.text() and "PURCHASE CONTRACT" not in buyer.text()
    assert "PURCHASE CONTRACT" in seller.text() and "SALES CONTRACT" not in seller.text()
