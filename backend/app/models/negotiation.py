"""Negotiation (M4 · S8, A-074, A-075): the two chat threads of a deal and
the strikes the leak filter records.

Every deal in negotiation has two threads, one per side: the buyer talks to
the desk, and the desk to the seller. Nothing is relayed as written: a
message that passes the filter is copied into the other thread with the
sender's company code; one the filter doubts waits for the desk; one it
blocks is refused and recorded as a strike (its text is not kept)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, JSON, BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

THREAD_SIDES = ("buyer", "seller")
#: ``own``: written by this side; ``relay``: a copy of the other side's
#: message; ``desk``: written by Corridor One X; ``system``: an event line.
MESSAGE_ORIGINS = ("own", "relay", "desk", "system")
#: ``held``: waiting for the desk; ``rejected``: the desk refused it.
MESSAGE_STATUSES = ("delivered", "held", "rejected")
MAX_MESSAGE = 2000


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        UniqueConstraint("deal_id", "side", name="uq_chat_threads_deal_side"),
        CheckConstraint(_in("side", THREAD_SIDES), name="ck_chat_threads_side"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE", name="fk_chat_threads_deal_id"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class ChatMessage(Base):
    """One line in one thread. Never edited or deleted: the thread is the
    record of what each side was told."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_thread_time", "thread_id", "created_at"),
        Index("ix_chat_messages_held", "status", "created_at"),
        CheckConstraint(_in("origin", MESSAGE_ORIGINS), name="ck_chat_messages_origin"),
        CheckConstraint(_in("status", MESSAGE_STATUSES), name="ck_chat_messages_status"),
        CheckConstraint("status <> 'rejected' OR review_note IS NOT NULL", name="ck_chat_messages_rejected_has_note"),
        CheckConstraint("(origin = 'relay') = (relayed_from_id IS NOT NULL)", name="ck_chat_messages_relay_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_threads.id", ondelete="CASCADE", name="fk_chat_messages_thread_id"), nullable=False
    )
    origin: Mapped[str] = mapped_column(String(6), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="delivered")
    # A trader's message: who wrote it and the company code the other side sees.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_chat_messages_author_user_id"), nullable=True
    )
    author_business_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="SET NULL", name="fk_chat_messages_author_business_id"), nullable=True
    )
    sender_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    # The desk's line, or the admin who released / rejected a held one.
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_chat_messages_admin_id"), nullable=True
    )
    relayed_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("chat_messages.id", ondelete="CASCADE", name="fk_chat_messages_relayed_from_id"), nullable=True
    )
    # What the leak filter found (REVIEW), for the desk.
    flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class LeakStrike(Base):
    """A message the leak filter blocked. Three within 90 days suspend the
    company (A-075). The text itself is not kept."""

    __tablename__ = "leak_strikes"
    __table_args__ = (Index("ix_leak_strikes_business_time", "business_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_leak_strikes_business_id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_leak_strikes_user_id"), nullable=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="SET NULL", name="fk_leak_strikes_deal_id"), nullable=True
    )
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


#: ``pending_desk`` → ``relayed`` (passed on, maybe at another margin) →
#: ``accepted`` / ``declined`` by the other side; ``rejected`` by the desk;
#: ``superseded`` by a newer counter from the same side.
COUNTER_STATUSES = ("pending_desk", "relayed", "accepted", "declined", "rejected", "superseded")
#: Still waiting on someone.
COUNTER_OPEN = ("pending_desk", "relayed")


class CounterOffer(Base):
    """A price change proposed by one side (CX-101, A-078). The proposer's
    price is in their own currency; ``implied_minor`` is what it means for
    the other side, back-solved through the deal's cost sheet at
    ``margin_pct``. Each side only ever sees its own price."""

    __tablename__ = "counter_offers"
    __table_args__ = (
        Index("ix_counter_offers_deal_time", "deal_id", "created_at"),
        Index("ix_counter_offers_status", "status", "created_at"),
        CheckConstraint(_in("side", THREAD_SIDES), name="ck_counter_offers_side"),
        CheckConstraint(_in("status", COUNTER_STATUSES), name="ck_counter_offers_status"),
        CheckConstraint("price_minor > 0 AND implied_minor > 0", name="ck_counter_offers_prices"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_counter_offers_quantity"),
        CheckConstraint("status <> 'rejected' OR decision_note IS NOT NULL", name="ck_counter_offers_rejected_has_note"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE", name="fk_counter_offers_deal_id"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    implied_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    implied_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    margin_pct: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2), nullable=False)
    status: Mapped[str] = mapped_column(String(14), nullable=False, default="pending_desk")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_counter_offers_created_by_user_id"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_counter_offers_decided_by"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


#: The sample's path (plan 7.3): seller → hub → split and seal → forwarded
#: under Corridor One X → buyer → reviewed.
SAMPLE_STATUSES = (
    "requested", "seller_dispatched", "at_hub", "split_sealed", "forwarded", "buyer_received", "reviewed",
)
SAMPLE_VERDICTS = ("passed", "failed")


class Sample(Base):
    """A sample on a deal in negotiation (CX-102). The hub keeps one sealed
    half (``retained_seal_no``) for disputes; the other half goes to the
    buyer under Corridor One X's name. The seller's courier reference names
    the seller, so only the desk sees it."""

    __tablename__ = "samples"
    __table_args__ = (
        Index("ix_samples_deal", "deal_id"),
        Index("ix_samples_status", "status"),
        CheckConstraint(_in("status", SAMPLE_STATUSES), name="ck_samples_status"),
        CheckConstraint("verdict IS NULL OR " + _in("verdict", SAMPLE_VERDICTS), name="ck_samples_verdict"),
        # Nothing leaves the hub until the retained half is sealed and numbered.
        CheckConstraint(
            "status NOT IN ('split_sealed', 'forwarded', 'buyer_received', 'reviewed') "
            "OR (retained_seal_no IS NOT NULL AND forward_seal_no IS NOT NULL)",
            name="ck_samples_sealed_before_forward",
        ),
        CheckConstraint("(status = 'reviewed') = (verdict IS NOT NULL)", name="ck_samples_reviewed_has_verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE", name="fk_samples_deal_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_samples_requested_by_user_id"), nullable=True
    )
    seller_courier_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retained_seal_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    forward_seal_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    forward_courier_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(6), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SampleEvent(Base):
    """One hop of a sample, timestamped with who recorded it. Insert only."""

    __tablename__ = "sample_events"
    __table_args__ = (
        Index("ix_sample_events_sample_time", "sample_id", "created_at"),
        CheckConstraint("actor_type IN ('user', 'admin')", name="ck_sample_events_actor_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sample_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("samples.id", ondelete="CASCADE", name="fk_sample_events_sample_id"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(5), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
