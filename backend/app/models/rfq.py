"""Requests for quotation (build plan 05): what a buyer asks for, which
sellers the desk matched it to, and the settings and country list the desk
works with."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class RfqStatus:
    draft = "draft"  # the buyer is still writing it; no deal, nothing charged
    submitted = "submitted"  # waiting for the desk
    held = "held"  # stopped for a compliance look before the desk works it
    matched = "matched"  # the desk confirmed sellers; they can see it
    rejected = "rejected"  # the desk refused it (refunded)
    unmatched = "unmatched"  # no seller fits (refunded)
    expired = "expired"  # the open period ran out

    ALL = (draft, submitted, held, matched, rejected, unmatched, expired)
    #: Waiting on the desk.
    QUEUE = (submitted, held)


RFQ_KINDS = ("listing", "open")
MATCH_STATUSES = ("proposed", "confirmed", "removed")
MATCH_SOURCES = ("rule", "desk")
#: How a buyer would like to pay. Fixed list; the contract sets the real terms (M4).
PAYMENT_TERMS = ("advance", "lc_sight", "lc_usance", "advance_balance_docs", "open_account")


class Rfq(Base):
    """A buyer's request. ``draft`` rows belong to no deal; submitting one
    creates its deal. Prices are integers in the currency's minor unit, per
    ``unit``."""

    __tablename__ = "rfqs"
    __table_args__ = (
        UniqueConstraint("deal_id", name="uq_rfqs_deal_id"),
        Index("ix_rfqs_buyer_time", "buyer_business_id", text("created_at DESC")),
        Index("ix_rfqs_queue", "status", "submitted_at"),
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in RfqStatus.ALL)})", name="ck_rfqs_status"),
        CheckConstraint("kind IN ('listing', 'open')", name="ck_rfqs_kind"),
        CheckConstraint("unit IN ('MT', 'kg', 'quintal')", name="ck_rfqs_unit"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_rfqs_quantity"),
        CheckConstraint(
            "(target_price_min IS NULL OR target_price_min >= 0) AND "
            "(target_price_max IS NULL OR (target_price_min IS NOT NULL AND target_price_max >= target_price_min))",
            name="ck_rfqs_target_price",
        ),
        CheckConstraint(
            "delivery_from IS NULL OR delivery_to IS NULL OR delivery_to >= delivery_from", name="ck_rfqs_window"
        ),
        # Once it leaves draft it has a deal and a submission time.
        CheckConstraint(
            "status = 'draft' OR (deal_id IS NOT NULL AND submitted_at IS NOT NULL)", name="ck_rfqs_submitted_has_deal"
        ),
        CheckConstraint(
            "status NOT IN ('rejected', 'held') OR desk_reason IS NOT NULL", name="ck_rfqs_desk_reason"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_rfqs_deal_id"), nullable=True
    )
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_rfqs_buyer_business_id"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_rfqs_created_by"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=RfqStatus.draft, server_default="draft")

    # ─── What is asked for ─────────────────────────────────────────
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    # The listing it was raised from (kind = listing).
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL", name="fk_rfqs_listing_id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The buyer's limits, as rows of the category template at the time:
    # [{"parameter_id", "value", "operator"}]. A snapshot, so a parameter
    # retired later does not change what was asked.
    specs: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="MT", server_default="MT")
    packaging: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Certificate types the buyer needs with the goods.
    certificate_type_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    # ─── Commercial ────────────────────────────────────────────────
    # For the desk only: a seller never sees what the buyer hopes to pay.
    target_price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    incoterms: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    payment_terms: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ─── Delivery ──────────────────────────────────────────────────
    delivery_country: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    destination_port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Desk ──────────────────────────────────────────────────────
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Why it is held or was rejected. A rejection reason is shown to the buyer.
    desk_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_rfqs_decided_by"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RfqMatch(Base):
    """A seller proposed for an RFQ. Nothing reaches the seller until a desk
    user confirms the match (plan 5.5)."""

    __tablename__ = "rfq_matches"
    __table_args__ = (
        UniqueConstraint("rfq_id", "seller_business_id", name="uq_rfq_matches_seller"),
        Index("ix_rfq_matches_seller", "seller_business_id", "status"),
        CheckConstraint("status IN ('proposed', 'confirmed', 'removed')", name="ck_rfq_matches_status"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_rfq_matches_score"),
        CheckConstraint("source IN ('rule', 'desk')", name="ck_rfq_matches_source"),
        CheckConstraint("status <> 'confirmed' OR confirmed_at IS NOT NULL", name="ck_rfq_matches_confirmed_has_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rfqs.id", ondelete="CASCADE", name="fk_rfq_matches_rfq_id"), nullable=False
    )
    seller_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_rfq_matches_seller_business_id"), nullable=False
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL", name="fk_rfq_matches_listing_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="proposed", server_default="proposed")
    source: Mapped[str] = mapped_column(String(5), nullable=False)
    # Each hard rule and how this listing met it: [{"rule", "detail"}].
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: 0–100 from ``rfq/ranking.py`` (CX-177); null for desk-added matches.
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    #: The score's parts: points, out of, and a sentence each.
    score_parts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_rfq_matches_confirmed_by"), nullable=True
    )
    # When the seller first opened it (the RFQ_VIEW debit).
    viewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class HeldCountry(Base):
    """A country whose RFQs stop for a compliance look (decision A-039).
    The list is the client's; it starts empty."""

    __tablename__ = "held_countries"
    __table_args__ = (CheckConstraint("length(code) = 2 AND code = upper(code)", name="ck_held_countries_code"),)

    code: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class TradeSetting(Base):
    """A number the desk works with that the client decides: how long an RFQ
    stays open, the margin floor, the FX buffer. ``is_placeholder`` until set."""

    __tablename__ = "trade_settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=4), nullable=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
