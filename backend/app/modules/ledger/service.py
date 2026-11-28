"""Posting to the trade ledger (CX-111, A-083).

:func:`post` is the only way money enters the books: it refuses lines that
don't net to zero in each currency, and a retry with the same idempotency
key returns the first posting instead of posting twice. :func:`reverse` is
the only correction. Postgres checks the balance again at commit
(``trg_ledger_entries_balanced``); both databases refuse updates and deletes."""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import utcnow
from app.models.ledger import ACCOUNTS, LEGS, LedgerEntry, LedgerTransaction


@dataclass(frozen=True)
class Line:
    account: str
    amount_minor: int
    currency: str
    leg: str | None = None


def _check(lines: list[Line]) -> None:
    if len(lines) < 2:
        raise Conflict("A ledger posting needs at least two lines.")
    totals: dict[str, int] = defaultdict(int)
    for line in lines:
        if line.account not in ACCOUNTS or (line.leg is not None and line.leg not in LEGS):
            raise Conflict(f"Unknown ledger account or leg: {line.account}, {line.leg}.")
        if not isinstance(line.amount_minor, int) or isinstance(line.amount_minor, bool) or line.amount_minor == 0:
            raise Conflict("Ledger amounts are whole minor units and never zero.")
        if len(line.currency) != 3 or not line.currency.isupper():
            raise Conflict("A ledger line needs a three-letter currency code.")
        totals[line.currency] += line.amount_minor
    unbalanced = {c: t for c, t in totals.items() if t != 0}
    if unbalanced:
        raise Conflict(f"The ledger lines don't balance: {unbalanced}.")


def _same(existing: list[LedgerEntry], lines: list[Line]) -> bool:
    key = lambda x: (x.account, x.leg or "", x.currency, x.amount_minor)  # noqa: E731
    return sorted(map(key, existing)) == sorted(map(key, lines))


async def entries_of(db: AsyncSession, transaction_id: uuid.UUID) -> list[LedgerEntry]:
    return list(await db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == transaction_id)))


async def post(
    db: AsyncSession, *, kind: str, memo: str, lines: list[Line], idempotency_key: str,
    deal_id: uuid.UUID | None = None, reference: tuple[str, str] | None = None, admin_id: uuid.UUID | None = None,
    reverses_id: uuid.UUID | None = None,
) -> LedgerTransaction:
    """Post one balanced transaction. The caller commits it with whatever it
    records. The same key with different lines is refused: a retry must be
    the same posting."""
    _check(lines)
    existing = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key == idempotency_key))
    if existing is not None:
        if not _same(await entries_of(db, existing.id), lines):
            raise Conflict("This posting key was already used for different amounts.")
        return existing
    now = utcnow()
    txn = LedgerTransaction(
        id=uuid.uuid4(), deal_id=deal_id, kind=kind, memo=memo[:300], idempotency_key=idempotency_key,
        reference_type=reference[0] if reference else None, reference_id=reference[1] if reference else None,
        created_by=admin_id, created_at=now, reverses_id=reverses_id,
    )
    db.add(txn)
    await db.flush()
    db.add_all([
        LedgerEntry(transaction_id=txn.id, deal_id=deal_id, account=l.account, leg=l.leg,
                    amount_minor=l.amount_minor, currency=l.currency, created_at=now)
        for l in lines
    ])
    await db.flush()
    return txn


async def reverse(db: AsyncSession, transaction_id: uuid.UUID | None, *, reason: str, admin_id: uuid.UUID) -> LedgerTransaction:
    """Correct a posting by posting its exact opposite. Once only; a reversal
    itself isn't reversed (post the right entry instead)."""
    original = await db.get(LedgerTransaction, transaction_id) if transaction_id else None
    if original is None:
        raise NotFound("Ledger transaction not found.")
    if original.reverses_id is not None:
        raise Conflict("A reversal can't be reversed. Post the correct entry instead.")
    if await db.scalar(select(LedgerTransaction.id).where(LedgerTransaction.reverses_id == original.id)):
        raise Conflict("This transaction has already been reversed.")
    if not reason.strip():
        raise BadRequest("Say why the posting is being reversed.")
    lines = [Line(e.account, -e.amount_minor, e.currency, e.leg) for e in await entries_of(db, original.id)]
    txn = await post(
        db, kind="reversal", memo=f"Reverses: {original.memo}. Reason: {reason.strip()}", lines=lines,
        idempotency_key=f"reversal:{original.id}", deal_id=original.deal_id,
        reference=("ledger_transaction", str(original.id)), admin_id=admin_id, reverses_id=original.id,
    )
    return txn


# ── Reading the books ────────────────────────────────────────────────


@dataclass(frozen=True)
class LegView:
    leg: str
    #: account → currency → balance in minor units (debit positive).
    balances: dict[str, dict[str, int]]


async def deal_books(db: AsyncSession, deal_id: uuid.UUID) -> tuple[list[LegView], dict[str, int]]:
    """A deal's matched pair: the buy leg and the sell leg (and Corridor One
    X's own lines) side by side, and the deal's total per currency, which is
    always zero."""
    rows = await db.execute(
        select(LedgerEntry.leg, LedgerEntry.account, LedgerEntry.currency, func.sum(LedgerEntry.amount_minor))
        .where(LedgerEntry.deal_id == deal_id)
        .group_by(LedgerEntry.leg, LedgerEntry.account, LedgerEntry.currency)
    )
    legs: dict[str, dict[str, dict[str, int]]] = {leg: defaultdict(dict) for leg in LEGS}
    totals: dict[str, int] = defaultdict(int)
    for leg, account, currency, amount in rows:
        legs[leg or "corridor"][account][currency] = int(amount)
        totals[currency] += int(amount)
    return [LegView(leg, dict(b)) for leg, b in legs.items()], dict(totals)


async def transactions_of(db: AsyncSession, deal_id: uuid.UUID) -> list[tuple[LedgerTransaction, list[LedgerEntry]]]:
    txns = list(await db.scalars(
        select(LedgerTransaction).where(LedgerTransaction.deal_id == deal_id).order_by(LedgerTransaction.created_at)
    ))
    return [(t, await entries_of(db, t.id)) for t in txns]
