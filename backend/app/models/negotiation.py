"""Negotiation (M4 · S8, A-074, A-075): the two chat threads of a deal and
the strikes the leak filter records.

Every deal in negotiation has two threads, one per side: the buyer talks to
the desk, and the desk to the seller. Nothing is relayed as written: a
message that passes the filter is copied into the other thread with the
sender's company code; one the filter doubts waits for the desk; one it
blocks is refused and recorded as a strike (its text is not kept)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    DDL,
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
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


#: A version's path (A-076): the desk drafts it, issues it to both sides,
#: and it is agreed when both accept. ``superseded`` when a later version is
#: agreed; ``declined`` when a side says no; ``withdrawn`` by the desk.
TERM_SHEET_STATUSES = ("draft", "issued", "agreed", "declined", "withdrawn", "superseded")
TERM_SHEET_OPEN = ("draft", "issued")
#: The terms. Frozen from issue: the code doesn't write them, and a trigger
#: refuses it at the database (``trg_term_sheets_frozen``).
TERM_FIELDS = (
    "product", "quality", "packaging", "quantity", "unit", "incoterm", "port_of_loading", "destination_port",
    "delivery_from", "delivery_to", "buyer_price_minor", "buyer_currency", "buyer_payment_terms",
    "seller_price_minor", "seller_currency", "seller_payment_terms", "margin_pct", "notes", "version",
    "deal_id", "content_sha256",
)


class TermSheet(Base):
    """One version of a deal's terms (CX-103, A-076): the single source for
    the LOIs and contracts that follow. Corridor One X is the counterparty
    to both sides, so a version holds both prices; each side is shown only
    its own. Once issued, its content is hashed and never changes; a change
    is a new version."""

    __tablename__ = "term_sheets"
    __table_args__ = (
        UniqueConstraint("deal_id", "version", name="uq_term_sheets_deal_version"),
        # One version being worked on, and one agreed, per deal.
        Index(
            "uq_term_sheets_open", "deal_id", unique=True,
            sqlite_where=text("status IN ('draft', 'issued')"), postgresql_where=text("status IN ('draft', 'issued')"),
        ),
        Index(
            "uq_term_sheets_agreed", "deal_id", unique=True,
            sqlite_where=text("status = 'agreed'"), postgresql_where=text("status = 'agreed'"),
        ),
        CheckConstraint(_in("status", TERM_SHEET_STATUSES), name="ck_term_sheets_status"),
        CheckConstraint("version > 0 AND quantity > 0", name="ck_term_sheets_positive"),
        CheckConstraint("buyer_price_minor > 0 AND seller_price_minor > 0", name="ck_term_sheets_prices"),
        CheckConstraint(
            "delivery_from IS NULL OR delivery_to IS NULL OR delivery_to >= delivery_from",
            name="ck_term_sheets_delivery_window",
        ),
        CheckConstraint("status IN ('draft', 'withdrawn') OR content_sha256 IS NOT NULL", name="ck_term_sheets_hashed_when_issued"),
        CheckConstraint(
            "status NOT IN ('agreed', 'superseded') OR "
            "(buyer_accepted_at IS NOT NULL AND seller_accepted_at IS NOT NULL AND agreed_at IS NOT NULL)",
            name="ck_term_sheets_agreed_by_both",
        ),
        CheckConstraint("status <> 'declined' OR decline_note IS NOT NULL", name="ck_term_sheets_declined_has_note"),
        CheckConstraint("status <> 'withdrawn' OR withdraw_note IS NOT NULL", name="ck_term_sheets_withdrawn_has_note"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_term_sheets_deal_id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")

    # ─── The goods ─────────────────────────────────────────────────
    product: Mapped[str] = mapped_column(String(200), nullable=False)
    quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    packaging: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)

    # ─── Delivery ──────────────────────────────────────────────────
    incoterm: Mapped[str] = mapped_column(String(3), nullable=False)
    port_of_loading: Mapped[str | None] = mapped_column(String(100), nullable=True)
    destination_port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ─── Each side's price, per unit, in its own currency ──────────
    buyer_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    buyer_payment_terms: Mapped[str] = mapped_column(String(30), nullable=False)
    seller_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seller_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    seller_payment_terms: Mapped[str] = mapped_column(String(30), nullable=False)
    # Desk only: the margin the two prices leave, through the deal's cost sheet.
    margin_pct: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SHA-256 of the canonical terms, set on issue. Both sides accept this hash.
    content_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_term_sheets_created_by"), nullable=True
    )
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_term_sheets_issued_by"), nullable=True
    )
    issued_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    buyer_accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_term_sheets_buyer_accepted_by"), nullable=True
    )
    buyer_accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    seller_accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_term_sheets_seller_accepted_by"), nullable=True
    )
    seller_accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    agreed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    declined_side: Mapped[str | None] = mapped_column(String(6), nullable=True)
    decline_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    withdraw_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def term_sheet_freeze_sql(dialect: str) -> list[str]:
    """The trigger that refuses any change to the terms of an issued version,
    for schemas built from the models (tests). Migration 0040 carries its own
    copy, as migrations never import app code."""
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in TERM_FIELDS)
        return [
            "CREATE TRIGGER trg_term_sheets_frozen BEFORE UPDATE ON term_sheets "
            f"WHEN OLD.content_sha256 IS NOT NULL AND ({changed}) "
            "BEGIN SELECT RAISE(ABORT, 'term_sheet_frozen'); END"
        ]
    changed = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in TERM_FIELDS)
    return [
        "CREATE FUNCTION term_sheets_frozen() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        f"IF OLD.content_sha256 IS NOT NULL AND ({changed}) THEN "
        "RAISE EXCEPTION 'term_sheet_frozen' USING ERRCODE = 'integrity_constraint_violation'; END IF; "
        "RETURN NEW; END $$",
        "CREATE TRIGGER trg_term_sheets_frozen BEFORE UPDATE ON term_sheets "
        "FOR EACH ROW EXECUTE FUNCTION term_sheets_frozen()",
    ]


for _dialect in ("sqlite", "postgresql"):
    for _sql in term_sheet_freeze_sql(_dialect):
        event.listen(TermSheet.__table__, "after_create", DDL(_sql).execute_if(dialect=_dialect))
