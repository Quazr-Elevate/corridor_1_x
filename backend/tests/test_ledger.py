"""The trade ledger (M5 · S10, CX-111, A-083): balanced, idempotent,
append-only, corrected only by reversal, and readable per deal as two legs."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_admin_accounts import _new_admin
from test_negotiation import _negotiating
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.core.errors import Conflict
from app.models import AdminAction, Deal, LedgerEntry
from app.modules.ledger.service import Line, post, reverse

# ₹83,160 × 500 MT received from the buyer.
RECEIPT = [Line("bank", 4_158_000_000, "INR"), Line("buyer_receivable", -4_158_000_000, "INR", "buyer")]


async def _deal_id(code: str) -> uuid.UUID:
    async with SessionLocal() as db:
        return await db.scalar(select(Deal.id).where(Deal.code == code))


async def test_only_balanced_postings_are_accepted():
    async with SessionLocal() as db:
        for lines in (
            [Line("bank", 100, "INR"), Line("buyer_receivable", -99, "INR")],          # off by one
            [Line("bank", 100, "INR")],                                                # one line
            [Line("bank", 100, "INR"), Line("buyer_receivable", -100, "AED")],         # nets per currency
            [Line("bank", 0, "INR"), Line("fees", 0, "INR")],                          # zero lines
            [Line("bank", 1.5, "INR"), Line("fees", -1.5, "INR")],                     # not minor units
            [Line("cash_box", 100, "INR"), Line("fees", -100, "INR")],                 # not an account
        ):
            with pytest.raises(Conflict):
                await post(db, kind="test", memo="x", lines=lines, idempotency_key=str(uuid.uuid4()))
        # Two currencies in one transaction are fine when each nets to zero.
        await post(db, kind="fx", memo="Conversion", idempotency_key="fx-1", lines=[
            Line("bank", 100_000, "USD"), Line("fx_gain_loss", -100_000, "USD"),
            Line("fx_gain_loss", 8_300_000, "INR"), Line("bank", -8_300_000, "INR"),
        ])
        await db.commit()


async def test_a_retry_posts_once_and_a_reused_key_with_other_amounts_is_refused():
    async with SessionLocal() as db:
        first = await post(db, kind="buyer_receipt", memo="Advance", lines=RECEIPT, idempotency_key="receipt:1")
        again = await post(db, kind="buyer_receipt", memo="Advance", lines=list(reversed(RECEIPT)), idempotency_key="receipt:1")
        assert again.id == first.id
        with pytest.raises(Conflict):
            await post(db, kind="buyer_receipt", memo="Advance", idempotency_key="receipt:1",
                       lines=[Line("bank", 1, "INR"), Line("buyer_receivable", -1, "INR")])
        await db.commit()
        assert len(list(await db.scalars(select(LedgerEntry)))) == 2


async def test_the_books_are_append_only():
    async with SessionLocal() as db:
        await post(db, kind="buyer_receipt", memo="Advance", lines=RECEIPT, idempotency_key="receipt:2")
        await db.commit()
    for stmt in (update(LedgerEntry).values(amount_minor=1), delete(LedgerEntry)):
        async with SessionLocal() as db:
            with pytest.raises((IntegrityError, DBAPIError)):
                await db.execute(stmt)
            await db.rollback()


async def test_a_deal_reads_as_two_legs_and_corrections_are_reversals(parties, admin_client, make_client):
    code = await _negotiating(parties, admin_client)
    deal_id = await _deal_id(code)
    async with SessionLocal() as db:
        receipt = await post(db, kind="buyer_receipt", memo="Advance from the buyer", lines=RECEIPT,
                             idempotency_key="receipt:3", deal_id=deal_id)
        await post(db, kind="seller_payable", memo="Purchase price owed", deal_id=deal_id, idempotency_key="payable:3",
                   lines=[Line("corridor_margin", 3_600_000_000, "INR", "seller"),
                          Line("seller_payable", -3_600_000_000, "INR", "seller")])
        await db.commit()

    _, finance = await _new_admin(admin_client, make_client, role="finance", email="fin@cor1x.test")
    _, manager = await _new_admin(admin_client, make_client, role="finance_manager", email="finmgr@cor1x.test")
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk@cor1x.test")
    assert (await desk.get(f"/admin/deals/{code}/ledger")).status_code == 403
    books = (await finance.get(f"/admin/deals/{code}/ledger")).json()
    assert books["balanced"] and books["totals"] == {"INR": 0}
    legs = {l["leg"]: l["balances"] for l in books["legs"]}
    assert legs["buyer"]["buyer_receivable"]["INR"] == -4_158_000_000
    assert legs["seller"]["seller_payable"]["INR"] == -3_600_000_000
    assert len(books["transactions"]) == 2

    # Finance reads; only a finance manager corrects, with a reason.
    url = f"/admin/ledger/{receipt.id}/reverse"
    body = {"reason": "Matched to the wrong deal; reposting."}
    assert (await finance.post(url, json=body)).status_code == 403
    r = await manager.post(url, json=body)
    assert r.status_code == 200, r.text
    assert sorted(e["amountMinor"] for e in r.json()["entries"]) == [-4_158_000_000, 4_158_000_000]
    assert (await manager.post(url, json=body)).status_code == 409  # once only
    assert (await manager.post(f"/admin/ledger/{r.json()['id']}/reverse", json=body)).status_code == 409
    books = (await finance.get(f"/admin/deals/{code}/ledger")).json()
    assert books["balanced"]
    assert {l["leg"]: l["balances"] for l in books["legs"]}["buyer"]["buyer_receivable"]["INR"] == 0
    assert [t["reversed"] for t in books["transactions"]][0] is True
    async with SessionLocal() as db:
        assert await db.scalar(select(AdminAction).where(AdminAction.action == "ledger.reversed"))


async def test_a_reversal_needs_a_reason():
    async with SessionLocal() as db:
        txn = await post(db, kind="buyer_receipt", memo="Advance", lines=RECEIPT, idempotency_key="receipt:4")
        with pytest.raises(Exception):
            await reverse(db, txn.id, reason="  ", admin_id=uuid.uuid4())
