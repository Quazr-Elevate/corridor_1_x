"""/deals/{code}/milestones — a party's own payment milestones (CX-110)."""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.negotiation import service as chat
from app.modules.payments import milestones
from app.modules.payments.schemas import MilestoneOut
from app.shared.schemas import ItemList, item_list

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/{code}/milestones", response_model=ItemList[MilestoneOut], response_model_by_alias=True)
async def own_milestones(code: str, user: CurrentUser, db: DbSession) -> ItemList[MilestoneOut]:
    """The buyer's: what it pays Corridor One X. The seller's: what Corridor
    One X pays it. Never the other side's."""
    p = await chat.party(db, user, code)
    return item_list([
        MilestoneOut(sequence=m.sequence, kind=m.kind, amount_minor=m.amount_minor, currency=m.currency,
                     due_event=m.due_event, due_days=m.due_days, due_at=m.due_at, status=m.status)
        for m in await milestones.of_deal(db, p.deal.id, leg=p.side)
    ])
