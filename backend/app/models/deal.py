"""The deal: one buyer request travelling from RFQ to close (build plan 05–16).
Its status changes only through ``app/modules/deals/machine.py``."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class DealStatus:
    RFQ_OPEN = "RFQ_OPEN"
    QUOTED = "QUOTED"
    NEGOTIATING = "NEGOTIATING"
    LOI_SIGNED = "LOI_SIGNED"
    CONTRACTED = "CONTRACTED"
    ADVANCE_PAID = "ADVANCE_PAID"
    IN_PRODUCTION = "IN_PRODUCTION"
    INSPECTED = "INSPECTED"
    SHIPPED = "SHIPPED"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    ACCEPTED = "ACCEPTED"
    SETTLED = "SETTLED"
    CLOSED = "CLOSED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"

    ALL = (
        RFQ_OPEN, QUOTED, NEGOTIATING, LOI_SIGNED, CONTRACTED, ADVANCE_PAID, IN_PRODUCTION, INSPECTED, SHIPPED,
        ARRIVED, DELIVERED, ACCEPTED, SETTLED, CLOSED, DISPUTED, CANCELLED,
    )
    #: Nothing leaves these.
    FINAL = (CLOSED, CANCELLED)


ACTOR_TYPES = ("user", "admin", "system")


class Deal(Base):
    """A trade in progress. Created when a buyer submits an RFQ. The seller
    is unknown until the buyer goes ahead with one offer (M4)."""

    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint("code", name="uq_deals_code"),
        Index("ix_deals_buyer_time", "buyer_business_id", text("created_at DESC")),
        Index("ix_deals_status", "status"),
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in DealStatus.ALL)})", name="ck_deals_status"),
        CheckConstraint(
            "seller_business_id IS NULL OR seller_business_id <> buyer_business_id", name="ck_deals_two_parties"
        ),
        CheckConstraint("status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="ck_deals_cancelled_has_reason"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # What people quote to each other and to the desk: ``DL-48291357``.
    code: Mapped[str] = mapped_column(String(12), nullable=False)
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT", name="fk_deals_buyer_business_id"), nullable=False
    )
    seller_business_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT", name="fk_deals_seller_business_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DealStatus.RFQ_OPEN)
    cancel_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Bumped on every transition; a stale writer loses.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DealEvent(Base):
    """One state change of a deal. Insert only: this is the deal's audit trail."""

    __tablename__ = "deal_events"
    __table_args__ = (
        Index("ix_deal_events_deal_time", "deal_id", "created_at"),
        CheckConstraint("actor_type IN ('user', 'admin', 'system')", name="ck_deal_events_actor_type"),
        CheckConstraint("(actor_type = 'system') = (actor_id IS NULL)", name="ck_deal_events_actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE", name="fk_deal_events_deal_id"), nullable=False
    )
    # NULL on the event that creates the deal.
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
