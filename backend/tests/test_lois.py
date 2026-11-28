"""LOIs (M4 · S9, CX-104, CX-106, CX-108, A-081): issued from the agreed
term sheet on lawyer-approved templates only, each naming only its own
party, signed in the app against the exact text's hash, countersigned by
Corridor One X, and lapsing together if not signed in five business days."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from conftest import sent_emails
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_admin_accounts import _new_admin
from test_quotes import parties  # noqa: F401  (fixture)
from test_term_sheets import _issued

from app.core.db import SessionLocal
from app.core.time import add_business_days, utcnow
from app.models import AdminAction, Deal, DealDocument, DocumentSignature, User
from app.modules.contracts.documents import lapse_due
from app.modules.masking import service as masking

SIGN = {"signerRole": "Director", "authorityConfirmed": True}


async def approve_templates(admin_client, codes=("loi_buy", "loi_sell")) -> None:
    for t in (await admin_client.get("/admin/contract-templates")).json()["items"]:
        if t["code"] in codes and t["status"] == "draft":
            r = await admin_client.post(f"/admin/contract-templates/{t['id']}/approve",
                                        json={"note": "Approved by A. Menon, Menon & Co, letter of 27 Nov 2026."})
            assert r.status_code == 200, r.text


async def agreed(p, admin_client, **changes) -> str:
    code, ts = await _issued(p, admin_client, **changes)
    for c in (p["buyer_client"], p["seller_client"]):
        r = await c.post(f"/deals/{code}/term-sheets/{ts['version']}/accept", json={"contentSha256": ts["contentSha256"]})
        assert r.status_code == 200, r.text
    return code


async def lois_out(p, admin_client) -> str:
    code = await agreed(p, admin_client)
    await approve_templates(admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/lois")
    assert r.status_code == 201, r.text
    return code


async def _legal_name(user_id: str) -> str:
    async with SessionLocal() as db:
        user = await db.get(User, uuid.UUID(user_id))
        return (await masking.party_for_document(db, user.business_id)).legal_name


def test_business_days_skip_the_weekend():
    friday = datetime(2026, 11, 27, 10, tzinfo=timezone.utc)
    assert add_business_days(friday, 1) == datetime(2026, 11, 30, 10, tzinfo=timezone.utc)
    assert add_business_days(friday, 5) == datetime(2026, 12, 4, 10, tzinfo=timezone.utc)


async def test_lois_wait_for_an_agreed_term_sheet_and_a_lawyer(parties, admin_client, make_client):
    p = parties
    code, _ = await _issued(p, admin_client)  # issued, not yet agreed
    await approve_templates(admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/lois")
    assert r.status_code == 409 and "agree a term sheet" in r.json()["detail"]

    # Templates: drafts until a super admin records a lawyer's approval.
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    rows = (await admin_client.get("/admin/contract-templates")).json()["items"]
    assert {t["code"] for t in rows} >= {"loi_buy", "loi_sell"}
    assert (await manager.post(f"/admin/contract-templates/{rows[0]['id']}/approve",
                               json={"note": "Approved by counsel."})).status_code == 403


async def test_no_lawyer_no_lois(parties, admin_client):
    code = await agreed(parties, admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/lois")
    assert r.status_code == 409 and "lawyer" in r.json()["detail"]


async def test_each_side_signs_its_own_loi_and_the_second_countersign_moves_the_deal(parties, admin_client, make_client):
    p = parties
    code = await lois_out(p, admin_client)
    assert sum("ready to sign" in m.subject for m in sent_emails()) == 2
    buyer_name, seller_name = await _legal_name(p["buyer"]["userId"]), await _legal_name(p["seller"]["userId"])

    buyer = (await p["buyer_client"].get(f"/deals/{code}/documents")).json()["items"]
    seller = (await p["seller_client"].get(f"/deals/{code}/documents")).json()["items"]
    assert len(buyer) == len(seller) == 1
    assert "LETTER OF INTENT TO PURCHASE" in buyer[0]["body"] and buyer_name in buyer[0]["body"]
    assert seller_name not in buyer[0]["body"] and buyer_name not in seller[0]["body"]
    # Each side's own price only.
    assert "83,160.00" in buyer[0]["body"] and "72,000.00" not in buyer[0]["body"]
    assert "72,000.00" in seller[0]["body"] and "83,160.00" not in seller[0]["body"]

    url = f"/deals/{code}/documents/{buyer[0]['id']}/sign"
    assert (await p["seller_client"].post(url, json={**SIGN, "contentSha256": buyer[0]["contentSha256"]})).status_code == 404
    r = await p["buyer_client"].post(url, json={**SIGN, "contentSha256": "0" * 64})
    assert r.status_code == 409 and "Reload it" in r.json()["detail"]
    r = await p["buyer_client"].post(url, json={**SIGN, "authorityConfirmed": False, "contentSha256": buyer[0]["contentSha256"]})
    assert r.status_code == 400
    r = await p["buyer_client"].post(url, json={**SIGN, "contentSha256": buyer[0]["contentSha256"]})
    assert r.status_code == 200 and r.json()["status"] == "party_signed" and r.json()["youSignedAt"]
    assert (await p["buyer_client"].post(url, json={**SIGN, "contentSha256": buyer[0]["contentSha256"]})).status_code == 409

    # Countersigning needs documents.sign: a desk manager, not the trade desk.
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    body = {**SIGN, "signerRole": "Authorised signatory", "contentSha256": buyer[0]["contentSha256"]}
    assert (await desk.post(f"/admin/documents/{buyer[0]['id']}/countersign", json=body)).status_code == 403
    # The seller hasn't signed yet: Corridor One X can't sign before the party.
    seller_body = {**body, "contentSha256": seller[0]["contentSha256"]}
    assert (await manager.post(f"/admin/documents/{seller[0]['id']}/countersign", json=seller_body)).status_code == 409
    r = await manager.post(f"/admin/documents/{buyer[0]['id']}/countersign", json=body)
    assert r.status_code == 200 and r.json()["status"] == "signed"

    await p["seller_client"].post(f"/deals/{code}/documents/{seller[0]['id']}/sign",
                                  json={**SIGN, "contentSha256": seller[0]["contentSha256"]})
    await manager.post(f"/admin/documents/{seller[0]['id']}/countersign", json=seller_body)
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        sigs = list(await db.scalars(select(DocumentSignature)))
        actions = list(await db.scalars(select(AdminAction.action).where(AdminAction.action.like("document.%"))))
    assert deal.status == "LOI_SIGNED"
    assert len(sigs) == 4 and all(s.content_sha256 in (buyer[0]["contentSha256"], seller[0]["contentSha256"]) for s in sigs)
    assert all(s.ip_prefix is None or s.ip_prefix.count(".") <= 3 for s in sigs)
    assert actions.count("document.countersigned") == 2


async def test_a_document_naming_the_other_side_is_never_created(parties, admin_client):
    p = parties
    seller_name = await _legal_name(p["seller"]["userId"])
    code = await agreed(p, admin_client, notes=f"Goods supplied by {seller_name}.")
    await approve_templates(admin_client)
    r = await admin_client.post(f"/admin/deals/{code}/lois")
    assert r.status_code == 409 and "identity" in r.json()["detail"]
    async with SessionLocal() as db:
        assert await db.scalar(select(DealDocument.id)) is None


async def test_unsigned_lois_lapse_together_and_can_be_issued_again(parties, admin_client):
    p = parties
    code = await lois_out(p, admin_client)
    doc = (await p["buyer_client"].get(f"/deals/{code}/documents")).json()["items"][0]
    await p["buyer_client"].post(f"/deals/{code}/documents/{doc['id']}/sign", json={**SIGN, "contentSha256": doc["contentSha256"]})
    async with SessionLocal() as db:
        assert await lapse_due(db, now=utcnow() + timedelta(days=8)) == 1
        await db.commit()
        rows = list(await db.scalars(select(DealDocument)))
        deal = await db.scalar(select(Deal).where(Deal.code == code))
    assert {r.status for r in rows} == {"void"} and deal.status == "NEGOTIATING"
    assert (await p["buyer_client"].get(f"/deals/{code}/documents")).json()["items"][0]["voidReason"] == "Not signed in time."
    assert (await admin_client.post(f"/admin/deals/{code}/lois")).status_code == 201


async def test_a_deal_whose_contracts_arent_signed_in_time_returns_to_negotiation(parties, admin_client, make_client):
    p = parties
    code = await lois_out(p, admin_client)
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    for c in (p["buyer_client"], p["seller_client"]):
        d = (await c.get(f"/deals/{code}/documents")).json()["items"][0]
        await c.post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
        await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})
    async with SessionLocal() as db:
        assert await lapse_due(db, now=utcnow() + timedelta(days=2)) == 0  # still inside the window
        assert await lapse_due(db, now=utcnow() + timedelta(days=8)) == 1
        await db.commit()
        deal = await db.scalar(select(Deal).where(Deal.code == code))
    assert deal.status == "NEGOTIATING"


async def test_a_newer_agreed_term_sheet_voids_open_lois(parties, admin_client):
    p = parties
    code = await lois_out(p, admin_client)
    v2 = (await admin_client.post(f"/admin/deals/{code}/term-sheets")).json()
    await admin_client.patch(f"/admin/term-sheets/{v2['id']}", json={"quantity": "250"})
    v2 = (await admin_client.post(f"/admin/term-sheets/{v2['id']}/issue")).json()
    for c in (p["buyer_client"], p["seller_client"]):
        await c.post(f"/deals/{code}/term-sheets/2/accept", json={"contentSha256": v2["contentSha256"]})
    async with SessionLocal() as db:
        reasons = set(await db.scalars(select(DealDocument.void_reason)))
    assert reasons == {"A newer term sheet was agreed."}


async def test_documents_and_signatures_cant_be_changed_in_the_database(parties, admin_client):
    p = parties
    code = await lois_out(p, admin_client)
    d = (await p["buyer_client"].get(f"/deals/{code}/documents")).json()["items"][0]
    await p["buyer_client"].post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
    async with SessionLocal() as db:
        with pytest.raises((IntegrityError, DBAPIError)):
            await db.execute(update(DealDocument).where(DealDocument.id == uuid.UUID(d["id"])).values(body="Changed."))
        await db.rollback()
    async with SessionLocal() as db:
        with pytest.raises((IntegrityError, DBAPIError)):
            await db.execute(update(DocumentSignature).values(signer_role="Someone else"))
        await db.rollback()
