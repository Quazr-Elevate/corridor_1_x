"""Payment milestones (M5 · S10, CX-110, A-083).

When a deal's contracts take effect, each side's payment terms become a list
of milestones: what the buyer pays Corridor One X, and when; what Corridor
One X pays the seller, less a retention held until acceptance. A milestone
names the event its due date runs from and the gate it opens (production,
shipment, the release of documents, a payout)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

MILESTONE_KINDS = (
    "advance", "balance", "cad", "lc_payment", "da_payment", "open_account", "escrow_funding", "retention",
)
DUE_EVENTS = ("contract_effective", "shipment", "documents", "acceptance")
GATES = ("start_production", "ship", "release_documents", "pay_seller", "release_retention")
#: ``open`` → ``cleared`` (buyer money received, CX-112) or ``paid`` (seller
#: payout made, CX-121); ``void`` if the deal is cancelled.
MILESTONE_STATUSES = ("open", "cleared", "paid", "void")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class PaymentMilestone(Base):
    __tablename__ = "payment_milestones"
    __table_args__ = (
        UniqueConstraint("deal_id", "leg", "sequence", name="uq_payment_milestones_deal_leg_sequence"),
        Index("ix_payment_milestones_status", "status", "leg"),
        CheckConstraint("leg IN ('buyer', 'seller')", name="ck_payment_milestones_leg"),
        CheckConstraint(_in("kind", MILESTONE_KINDS), name="ck_payment_milestones_kind"),
        CheckConstraint(_in("due_event", DUE_EVENTS), name="ck_payment_milestones_due_event"),
        CheckConstraint(_in("gate", GATES), name="ck_payment_milestones_gate"),
        CheckConstraint(_in("status", MILESTONE_STATUSES), name="ck_payment_milestones_status"),
        CheckConstraint("amount_minor > 0 AND due_days >= 0 AND sequence > 0", name="ck_payment_milestones_amounts"),
        # Buyer money is cleared; seller money is paid. Never the other way round.
        CheckConstraint(
            "(status <> 'cleared' OR leg = 'buyer') AND (status <> 'paid' OR leg = 'seller')",
            name="ck_payment_milestones_status_leg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_payment_milestones_deal_id"), nullable=False
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deal_documents.id", ondelete="RESTRICT", name="fk_payment_milestones_contract_id"),
        nullable=False,
    )
    #: ``buyer``: the buyer pays Corridor One X. ``seller``: Corridor One X pays the seller.
    leg: Mapped[str] = mapped_column(String(6), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    #: The due date is ``due_days`` after this event, once it happens.
    due_event: Mapped[str] = mapped_column(String(20), nullable=False)
    due_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    gate: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    cleared_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
