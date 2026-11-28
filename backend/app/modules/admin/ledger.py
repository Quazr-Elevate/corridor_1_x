"""/admin/… — the trade ledger as finance reads and corrects it (CX-111, A-083)."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.core.security import parse_uuid
from app.models.ledger import LedgerTransaction
from app.modules.admin import service as audit
from app.modules.admin.deps import CanCorrectLedger, CanViewFinance
from app.modules.auth.deps import DbSession
from app.modules.ledger import service as ledger
from app.modules.ledger.schemas import DealBooksOut, EntryOut, LegOut, ReverseIn, TransactionOut
from app.modules.negotiation import service as deals
from app.modules.payments import milestones
from app.modules.payments.schemas import DeskMilestoneOut
from app.shared.schemas import ItemList, item_list

router = APIRouter()


async def _books(db, deal) -> DealBooksOut:
    legs, totals = await ledger.deal_books(db, deal.id)
    reversed_ids = set(await db.scalars(
        select(LedgerTransaction.reverses_id).where(
            LedgerTransaction.deal_id == deal.id, LedgerTransaction.reverses_id.is_not(None)
        )
    ))
    return DealBooksOut(
        deal_code=deal.code,
        legs=[LegOut(leg=l.leg, balances=l.balances) for l in legs],
        totals=totals, balanced=all(v == 0 for v in totals.values()),
        transactions=[
            TransactionOut(
                id=str(t.id), kind=t.kind, memo=t.memo, reverses_id=str(t.reverses_id) if t.reverses_id else None,
                reversed=t.id in reversed_ids, reference_type=t.reference_type, reference_id=t.reference_id,
                created_at=t.created_at,
                entries=[EntryOut(account=e.account, leg=e.leg, amount_minor=e.amount_minor, currency=e.currency)
                         for e in entries],
            )
            for t, entries in await ledger.transactions_of(db, deal.id)
        ],
    )


@router.get("/deals/{code}/ledger", response_model=DealBooksOut, response_model_by_alias=True)
async def deal_ledger(code: str, _: CanViewFinance, db: DbSession) -> DealBooksOut:
    """A deal's books: the buy and sell legs side by side, every transaction,
    and whether each currency nets to zero."""
    return await _books(db, await deals.deal_by_code(db, code))


@router.post("/ledger/{transaction_id}/reverse", response_model=TransactionOut, response_model_by_alias=True)
async def reverse_transaction(transaction_id: str, payload: ReverseIn, admin: CanCorrectLedger, db: DbSession) -> TransactionOut:
    """Correct a posting by posting its opposite, with a reason (finance manager)."""
    txn = await ledger.reverse(db, parse_uuid(transaction_id), reason=payload.reason, admin_id=admin.id)
    audit.record_action(db, admin=admin, action="ledger.reversed", target_type="ledger_transaction",
                        target_id=txn.reverses_id, reason=payload.reason, details={"reversal": str(txn.id)})
    await db.commit()
    entries = await ledger.entries_of(db, txn.id)
    return TransactionOut(
        id=str(txn.id), kind=txn.kind, memo=txn.memo, reverses_id=str(txn.reverses_id), reversed=False,
        reference_type=txn.reference_type, reference_id=txn.reference_id, created_at=txn.created_at,
        entries=[EntryOut(account=e.account, leg=e.leg, amount_minor=e.amount_minor, currency=e.currency) for e in entries],
    )


@router.get("/deals/{code}/milestones", response_model=ItemList[DeskMilestoneOut], response_model_by_alias=True)
async def deal_milestones(code: str, _: CanViewFinance, db: DbSession) -> ItemList[DeskMilestoneOut]:
    """Both legs' payment milestones, buyer first, in order."""
    deal = await deals.deal_by_code(db, code)
    return item_list([
        DeskMilestoneOut(id=str(m.id), leg=m.leg, sequence=m.sequence, kind=m.kind, amount_minor=m.amount_minor,
                         currency=m.currency, due_event=m.due_event, due_days=m.due_days, due_at=m.due_at,
                         gate=m.gate, status=m.status, cleared_at=m.cleared_at)
        for m in await milestones.of_deal(db, deal.id)
    ])
