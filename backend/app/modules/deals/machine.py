"""Deal status: the one place a deal changes state (CX-089).

The table below is the diagram in ``docs/07_development_flow.md`` §8, edge
for edge. Nothing else assigns ``deal.status``; every move writes a
``deal_events`` row in the caller's transaction.

    RFQ_OPEN → QUOTED → NEGOTIATING ⇄ LOI_SIGNED → CONTRACTED → ADVANCE_PAID
      → IN_PRODUCTION → INSPECTED → SHIPPED → ARRIVED → DELIVERED → ACCEPTED
      → SETTLED → CLOSED

    INSPECTED, SHIPPED, ARRIVED, DELIVERED → DISPUTED → ACCEPTED
    RFQ_OPEN, QUOTED, NEGOTIATING, CONTRACTED, ADVANCE_PAID → CANCELLED
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict
from app.core.time import utcnow
from app.models.deal import Deal, DealEvent
from app.models.deal import DealStatus as S

#: (from, to) → the action recorded on the event.
MOVES: dict[tuple[str, str], str] = {
    (S.RFQ_OPEN, S.QUOTED): "offer_published",
    (S.QUOTED, S.NEGOTIATING): "negotiation_started",
    (S.NEGOTIATING, S.LOI_SIGNED): "lois_signed",
    (S.LOI_SIGNED, S.NEGOTIATING): "loi_lapsed",
    (S.LOI_SIGNED, S.CONTRACTED): "contracts_effective",
    (S.CONTRACTED, S.ADVANCE_PAID): "buyer_milestone_cleared",
    (S.ADVANCE_PAID, S.IN_PRODUCTION): "seller_advance_sent",
    (S.IN_PRODUCTION, S.INSPECTED): "inspection_passed",
    (S.INSPECTED, S.SHIPPED): "shipped",
    (S.SHIPPED, S.ARRIVED): "arrived",
    (S.ARRIVED, S.DELIVERED): "delivered",
    (S.DELIVERED, S.ACCEPTED): "accepted",
    (S.ACCEPTED, S.SETTLED): "settled",
    (S.SETTLED, S.CLOSED): "closed",
    (S.INSPECTED, S.DISPUTED): "dispute_opened",
    (S.SHIPPED, S.DISPUTED): "dispute_opened",
    (S.ARRIVED, S.DISPUTED): "dispute_opened",
    (S.DELIVERED, S.DISPUTED): "dispute_opened",
    (S.DISPUTED, S.ACCEPTED): "claim_settled",
    (S.RFQ_OPEN, S.CANCELLED): "cancelled",
    (S.QUOTED, S.CANCELLED): "cancelled",
    (S.NEGOTIATING, S.CANCELLED): "cancelled",
    (S.CONTRACTED, S.CANCELLED): "cancelled",
    (S.ADVANCE_PAID, S.CANCELLED): "cancelled",
}

_CODE_ATTEMPTS = 8


@dataclass(frozen=True)
class Actor:
    """Who moved the deal: a trader, an admin, or the system (a job)."""

    type: str
    id: uuid.UUID | None

    @classmethod
    def user(cls, user_id: uuid.UUID) -> Actor:
        return cls("user", user_id)

    @classmethod
    def admin(cls, admin_id: uuid.UUID) -> Actor:
        return cls("admin", admin_id)

    @classmethod
    def system(cls) -> Actor:
        return cls("system", None)


def can_move(current: str, to: str) -> bool:
    return (current, to) in MOVES


async def open_deal(db: AsyncSession, buyer_business_id: uuid.UUID, actor: Actor) -> Deal:
    """A new deal in RFQ_OPEN, with the event that records its start."""
    deal = Deal(id=uuid.uuid4(), code=await _new_code(db), buyer_business_id=buyer_business_id, status=S.RFQ_OPEN)
    db.add(deal)
    db.add(_event(deal, None, S.RFQ_OPEN, "rfq_submitted", actor, None))
    return deal


def transition(
    db: AsyncSession,
    deal: Deal,
    to: str,
    *,
    actor: Actor,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """Move ``deal`` to ``to`` and record it, or raise :class:`Conflict` when
    the table has no such edge. A cancellation needs a reason."""
    current = deal.status
    action = MOVES.get((current, to))
    if action is None:
        raise Conflict(f"A deal that is {_label(current)} cannot move to {_label(to)}.")
    if to == S.CANCELLED:
        if not (reason and reason.strip()):
            raise BadRequest("A cancellation needs a reason.")
        deal.cancel_reason = reason.strip()[:200]
        details = {**(details or {}), "reason": deal.cancel_reason}
    deal.status = to
    deal.version += 1
    deal.updated_at = utcnow()
    db.add(_event(deal, current, to, action, actor, details))


def _event(deal: Deal, current: str | None, to: str, action: str, actor: Actor, details: dict | None) -> DealEvent:
    return DealEvent(
        deal_id=deal.id, from_status=current, to_status=to, action=action, actor_type=actor.type,
        actor_id=actor.id, details=details, created_at=utcnow(),
    )


def _label(status: str) -> str:
    return status.replace("_", " ").lower()


async def _new_code(db: AsyncSession) -> str:
    """``DL-48291357``: random, so a code says nothing about how many deals exist."""
    for _ in range(_CODE_ATTEMPTS):
        code = f"DL-{secrets.randbelow(10**8):08d}"
        if await db.scalar(select(Deal.id).where(Deal.code == code)) is None:
            return code
    raise Conflict("Could not issue a deal code. Try again.")
