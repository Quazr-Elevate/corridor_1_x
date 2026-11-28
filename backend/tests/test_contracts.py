"""Contracts (M4 · S9, CX-105, CX-109, A-081): issued once both LOIs are
signed, refused unless they mirror (a 422 naming the field), held above the
legal-review threshold until a reviewer is recorded, and effective together
in one transaction when Corridor One X countersigns the second."""
from __future__ import annotations

from datetime import timedelta

from conftest import sent_emails
from sqlalchemy import select
from test_admin_accounts import _new_admin
from test_lois import SIGN, approve_templates, lois_out
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models import Deal, DealDocument
from app.modules.contracts.documents import lapse_due

TERMS = {
    "tolerancePct": "5", "shipmentFrom": "2027-02-01", "shipmentTo": "2027-03-15", "inspectionAgency": "SGS",
    "inspectionPoint": "Port of loading", "latePenaltyPct": "2", "qualityPenaltyPct": "1", "claimWindowDays": 30,
    "governingLaw": "England and Wales", "seat": "London (LCIA)", "forceMajeure": "GAFTA 125",
}
# The quote fixture's buyer pays ₹83,160 and the seller gets ₹72,000 a MT: the
# seller's contract is smaller, so the same rates don't mirror (rules 7 and 8).
PURCHASE = {**TERMS, "latePenaltyPct": "2.5", "qualityPenaltyPct": "1.2", "claimWindowDays": 45}
REVIEWED = "Reviewed by A. Menon, Menon & Co, on 28 Nov 2026."


async def lois_signed(p, admin_client, manager) -> str:
    code = await lois_out(p, admin_client)
    for c in (p["buyer_client"], p["seller_client"]):
        d = (await c.get(f"/deals/{code}/documents")).json()["items"][0]
        await c.post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
        r = await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})
        assert r.status_code == 200, r.text
    await approve_templates(admin_client, codes=("sales", "purchase"))
    return code


async def test_contracts_mirror_then_take_effect_together(parties, admin_client, make_client):
    p = parties
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    code = await lois_signed(p, admin_client, manager)
    url = f"/admin/deals/{code}/contracts"

    # Same rates on a smaller purchase contract: refused, naming the field.
    r = await admin_client.post(url, json={"sales": TERMS, "purchase": TERMS, "legalReviewNote": REVIEWED})
    assert r.status_code == 422 and r.json()["code"] == "contract.mirror"
    assert r.json()["fields"][0]["field"] == "purchase.late_penalty_pct"
    r = await admin_client.post(url, json={"sales": TERMS, "purchase": {**PURCHASE, "shipmentTo": "2027-04-01"},
                                           "legalReviewNote": REVIEWED})
    assert r.status_code == 422 and r.json()["fields"][0]["field"] == "purchase.shipment_to"
    # ₹83,160 × 500 MT is above the USD 250,000 placeholder: a reviewer must be recorded.
    r = await admin_client.post(url, json={"sales": TERMS, "purchase": PURCHASE})
    assert r.status_code == 409 and r.json()["code"] == "contract.legal_review"

    sent = len(sent_emails())
    r = await admin_client.post(url, json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})
    assert r.status_code == 201, r.text
    assert len(sent_emails()) == sent + 2

    buyer = [d for d in (await p["buyer_client"].get(f"/deals/{code}/documents")).json()["items"] if d["kind"] == "contract"]
    seller = [d for d in (await p["seller_client"].get(f"/deals/{code}/documents")).json()["items"] if d["kind"] == "contract"]
    assert "SALES CONTRACT" in buyer[0]["body"] and "PURCHASE CONTRACT" in seller[0]["body"]
    assert "2.5 % of the contract value" in seller[0]["body"] and "2.5 %" not in buyer[0]["body"]

    for c, d in ((p["buyer_client"], buyer[0]), (p["seller_client"], seller[0])):
        await c.post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
    r = await manager.post(f"/admin/documents/{buyer[0]['id']}/countersign", json={**SIGN, "contentSha256": buyer[0]["contentSha256"]})
    assert r.json()["status"] == "signed" and r.json()["effectiveAt"] is None  # not alone
    r = await manager.post(f"/admin/documents/{seller[0]['id']}/countersign", json={**SIGN, "contentSha256": seller[0]["contentSha256"]})
    assert r.json()["status"] == "effective"
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        contracts = list(await db.scalars(select(DealDocument).where(DealDocument.kind == "contract")))
    assert deal.status == "CONTRACTED"
    assert {c.status for c in contracts} == {"effective"} and len({c.effective_at for c in contracts}) == 1

    # An effective contract can't be voided.
    r = await admin_client.post(f"/admin/documents/{buyer[0]['id']}/void", json={"reason": "Trying to undo it."})
    assert r.status_code == 409


async def test_contracts_wait_for_signed_lois(parties, admin_client):
    code = await lois_out(parties, admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/contracts",
                                json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})
    assert r.status_code == 409 and "both LOIs" in r.json()["detail"]


async def test_unsigned_contracts_lapse_with_the_lois(parties, admin_client, make_client):
    p = parties
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    code = await lois_signed(p, admin_client, manager)
    r = await admin_client.post(f"/admin/deals/{code}/contracts",
                                json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})
    assert r.status_code == 201
    async with SessionLocal() as db:
        assert await lapse_due(db, now=utcnow() + timedelta(days=8)) == 1
        await db.commit()
        statuses = set(await db.scalars(select(DealDocument.status)))
        deal = await db.scalar(select(Deal).where(Deal.code == code))
    assert statuses == {"void"} and deal.status == "NEGOTIATING"


async def test_a_bad_shipment_window_is_refused_before_anything_runs(parties, admin_client):
    r = await admin_client.post("/admin/deals/XX-000000/contracts", json={
        "sales": {**TERMS, "shipmentTo": "2027-01-01"}, "purchase": PURCHASE,
    })
    assert r.status_code == 422
