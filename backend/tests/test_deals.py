"""The deal state machine (CX-089): every edge of the table is allowed, every
other move is refused, and each change leaves an event."""
from __future__ import annotations

import uuid
from itertools import product

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.core.errors import BadRequest, Conflict
from app.models import Business, Deal, DealEvent, DealStatus
from app.modules.deals import machine
from app.modules.deals.machine import MOVES, Actor

S = DealStatus
ALL_PAIRS = [(a, b) for a, b in product(S.ALL, S.ALL)]


async def _deal(db, status=S.RFQ_OPEN) -> Deal:
    buyer = Business(id=uuid.uuid4(), country="IN")
    db.add(buyer)
    await db.flush()
    deal = await machine.open_deal(db, buyer.id, Actor.system())
    await db.flush()
    deal.status = status  # the test's starting point; production code never does this
    if status == S.CANCELLED:
        deal.cancel_reason = "set up as cancelled"  # the CHECK wants one
    return deal


def test_the_table_is_the_diagram():
    """docs/07_development_flow.md §8, counted: 24 edges, no way out of the
    two final states, and a dispute only from the four delivery stages."""
    assert len(MOVES) == 24
    assert not [pair for pair in MOVES if pair[0] in S.FINAL]
    assert {a for (a, b) in MOVES if b == S.DISPUTED} == {S.INSPECTED, S.SHIPPED, S.ARRIVED, S.DELIVERED}
    assert {a for (a, b) in MOVES if b == S.CANCELLED} == {
        S.RFQ_OPEN, S.QUOTED, S.NEGOTIATING, S.CONTRACTED, S.ADVANCE_PAID,
    }
    assert MOVES[(S.LOI_SIGNED, S.NEGOTIATING)] == "loi_lapsed"  # the one step backwards
    # Every status is reachable from RFQ_OPEN.
    seen, frontier = {S.RFQ_OPEN}, [S.RFQ_OPEN]
    while frontier:
        here = frontier.pop()
        for (a, b) in MOVES:
            if a == here and b not in seen:
                seen.add(b)
                frontier.append(b)
    assert seen == set(S.ALL)


@pytest.mark.parametrize("current, to", sorted(MOVES))
async def test_every_edge_moves_and_is_recorded(current, to):
    async with SessionLocal() as db:
        deal = await _deal(db, current)
        admin = uuid.uuid4()
        machine.transition(db, deal, to, actor=Actor.admin(admin), reason="Buyer withdrew", details={"note": "x"})
        await db.flush()
        assert deal.status == to and deal.version == 2
        event = (await db.scalars(select(DealEvent).where(DealEvent.deal_id == deal.id).order_by(DealEvent.created_at))).all()[-1]
        assert (event.from_status, event.to_status, event.action) == (current, to, MOVES[(current, to)])
        assert (event.actor_type, event.actor_id) == ("admin", admin)
        if to == S.CANCELLED:
            assert deal.cancel_reason == "Buyer withdrew" and event.details == {"note": "x", "reason": "Buyer withdrew"}
        else:
            assert deal.cancel_reason is None


@pytest.mark.parametrize("current, to", [pair for pair in ALL_PAIRS if pair not in MOVES])
async def test_every_other_move_is_refused(current, to):
    async with SessionLocal() as db:
        deal = await _deal(db, current)
        await db.flush()
        with pytest.raises(Conflict):
            machine.transition(db, deal, to, actor=Actor.system(), reason="x")
        assert deal.status == current and deal.version == 1
        events = list(await db.scalars(select(DealEvent).where(DealEvent.deal_id == deal.id)))
        assert len(events) == 1  # only the one that opened it


async def test_a_cancellation_needs_a_reason_and_a_new_deal_starts_with_an_event():
    async with SessionLocal() as db:
        deal = await _deal(db)
        (opened,) = list(await db.scalars(select(DealEvent).where(DealEvent.deal_id == deal.id)))
        assert (opened.from_status, opened.to_status, opened.action, opened.actor_type) == (
            None, S.RFQ_OPEN, "rfq_submitted", "system",
        )
        assert deal.code.startswith("DL-") and len(deal.code) == 11 and deal.code[3:].isdigit()
        for reason in (None, "", "   "):
            with pytest.raises(BadRequest):
                machine.transition(db, deal, S.CANCELLED, actor=Actor.system(), reason=reason)
        assert deal.status == S.RFQ_OPEN


async def test_the_database_refuses_an_unknown_status_and_a_reasonless_cancel():
    async with SessionLocal() as db:
        buyer = Business(id=uuid.uuid4(), country="IN")
        db.add(buyer)
        await db.commit()
    row = dict(id=uuid.uuid4(), code="DL-00000001", buyer_business_id=buyer.id, version=1)
    for values, name in (
        ({"status": "PAID"}, "ck_deals_status"),
        ({"status": "CANCELLED"}, "ck_deals_cancelled_has_reason"),
        ({"status": "RFQ_OPEN", "seller_business_id": buyer.id}, "ck_deals_two_parties"),
    ):
        async with SessionLocal() as db:
            with pytest.raises(IntegrityError) as err:
                await db.execute(insert(Deal).values(**row, **values))
            assert name in str(err.value.orig)
