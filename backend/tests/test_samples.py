"""Samples (M4 · S8, CX-102, A-077): the buyer asks and pays in credits, the
seller ships to the hub, the hub splits and seals, keeps one half and
forwards the other under Corridor One X's name, and the buyer records a
verdict. Every hop is timestamped; each side sees only its own leg."""
from __future__ import annotations

import uuid

import pytest
from conftest import sent_emails
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from test_admin_accounts import _new_admin
from test_negotiation import _negotiating
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.models import AdminAction, Sample, SampleEvent
from app.modules.credits import service as credits


async def _balance(c) -> int:
    return (await c.get("/wallet")).json()["balance"]


async def _requested(p, admin_client) -> tuple[str, str]:
    code = await _negotiating(p, admin_client)
    r = await p["buyer_client"].post(f"/deals/{code}/samples")
    assert r.status_code == 201, r.text
    return code, r.json()["id"]


async def test_the_full_chain_with_each_side_seeing_its_own_leg(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    before = await _balance(p["buyer_client"])
    r = await p["buyer_client"].post(f"/deals/{code}/samples")
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert await _balance(p["buyer_client"]) == before - 5  # SAMPLE_FEE
    assert any("Please send a sample" in m.subject for m in sent_emails())
    # One open sample at a time.
    assert (await p["buyer_client"].post(f"/deals/{code}/samples")).status_code == 409

    seller = (await p["seller_client"].get(f"/deals/{code}/samples")).json()["items"][0]
    assert seller["status"] == "requested" and seller["hubAddress"]
    assert (await p["buyer_client"].get(f"/deals/{code}/samples")).json()["items"][0]["hubAddress"] is None

    # Only the seller dispatches; only the buyer reviews.
    url = f"/deals/{code}/samples/{sid}"
    assert (await p["buyer_client"].post(f"{url}/dispatch", json={"courierRef": "DTDC D1234567"})).status_code == 404
    r = await p["seller_client"].post(f"{url}/dispatch", json={"courierRef": "DTDC D1234567"})
    assert r.status_code == 200 and r.json()["status"] == "seller_dispatched" and r.json()["courierRef"] == "DTDC D1234567"

    # The buyer sees neither the seller's courier nor that it reached the hub.
    buyer = (await p["buyer_client"].get(f"/deals/{code}/samples")).json()["items"][0]
    assert buyer["status"] == "requested" and buyer["courierRef"] is None and "D1234567" not in str(buyer)

    assert (await admin_client.post(f"/admin/samples/{sid}/at-hub")).status_code == 200
    # Forwarding before sealing is refused.
    r = await admin_client.post(f"/admin/samples/{sid}/forward", json={"courierRef": "BLUEDART 99887766"})
    assert r.status_code == 409
    r = await admin_client.post(f"/admin/samples/{sid}/seal", json={"retainedSealNo": "SEAL-0001", "forwardSealNo": "SEAL-0001"})
    assert r.status_code == 400  # two halves, two seals
    r = await admin_client.post(f"/admin/samples/{sid}/seal", json={"retainedSealNo": "SEAL-0001", "forwardSealNo": "SEAL-0002"})
    assert r.status_code == 200 and r.json()["retainedSealNo"] == "SEAL-0001"
    r = await admin_client.post(f"/admin/samples/{sid}/forward", json={"courierRef": "BLUEDART 99887766"})
    assert r.status_code == 200 and r.json()["status"] == "forwarded"
    assert any("on its way" in m.subject for m in sent_emails())

    buyer = (await p["buyer_client"].get(f"/deals/{code}/samples")).json()["items"][0]
    assert buyer["status"] == "forwarded" and buyer["forwardCourierRef"] == "BLUEDART 99887766"
    seller = (await p["seller_client"].get(f"/deals/{code}/samples")).json()["items"][0]
    assert seller["forwardCourierRef"] is None and "99887766" not in str(seller) and "SEAL" not in str(seller)

    # Not received yet: the buyer can't review.
    assert (await p["buyer_client"].post(f"{url}/review", json={"verdict": "passed"})).status_code == 409
    assert (await admin_client.post(f"/admin/samples/{sid}/received")).status_code == 200
    r = await p["buyer_client"].post(f"{url}/review", json={"verdict": "passed", "note": "Moisture 11.5%, grain length good."})
    assert r.status_code == 200 and r.json()["status"] == "reviewed" and r.json()["verdict"] == "passed"
    assert any("reviewed the sample" in m.subject for m in sent_emails())
    seller = (await p["seller_client"].get(f"/deals/{code}/samples")).json()["items"][0]
    assert seller["verdict"] == "passed"
    assert [h["status"] for h in seller["hops"]] == ["requested", "seller_dispatched", "at_hub", "reviewed"]

    # The desk sees every hop and audit lines for its own.
    desk = (await admin_client.get(f"/admin/deals/{code}/samples")).json()["items"][0]
    assert [h["status"] for h in desk["hops"]] == [
        "requested", "seller_dispatched", "at_hub", "split_sealed", "forwarded", "buyer_received", "reviewed",
    ]
    assert (await admin_client.get("/admin/samples")).json()["items"] == []  # nothing open
    async with SessionLocal() as db:
        actions = set(await db.scalars(select(AdminAction.action).where(AdminAction.action.like("sample.%"))))
    assert actions == {"sample.at_hub", "sample.sealed", "sample.forwarded", "sample.received"}
    # A new sample may be asked for once the last is reviewed.
    assert (await p["buyer_client"].post(f"/deals/{code}/samples")).status_code == 201


async def test_a_short_balance_is_402_and_creates_nothing(parties, admin_client):
    p = parties
    code = await _negotiating(p, admin_client)
    bal = await _balance(p["buyer_client"])
    async with SessionLocal() as db:
        await credits._post(db, uuid.UUID(p["buyer"]["businessId"]), "ADJUSTMENT", -bal, idempotency_key=f"t-{uuid.uuid4()}")
        await db.commit()
    r = await p["buyer_client"].post(f"/deals/{code}/samples")
    assert r.status_code == 402
    async with SessionLocal() as db:
        assert await db.scalar(select(Sample.id)) is None


async def test_the_seller_cant_ask_and_outsiders_see_nothing(parties, admin_client, make_client):
    p = parties
    code, sid = await _requested(p, admin_client)
    assert (await p["seller_client"].post(f"/deals/{code}/samples")).status_code == 404
    assert (await make_client().get(f"/deals/{code}/samples")).status_code == 401
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    assert (await desk.get("/admin/samples")).status_code == 200
    _, kyb = await _new_admin(admin_client, make_client, role="reviewer", email="kyb@cor1x.test")
    assert (await kyb.post(f"/admin/samples/{sid}/at-hub")).status_code == 403


async def test_the_database_refuses_a_forwarded_sample_without_seals(parties, admin_client):
    p = parties
    _, sid = await _requested(p, admin_client)
    async with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            await db.execute(update(Sample).where(Sample.id == uuid.UUID(sid)).values(status="forwarded"))
            await db.flush()
        await db.rollback()
    async with SessionLocal() as db:
        assert len(list(await db.scalars(select(SampleEvent)))) == 1  # just "requested"
