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
