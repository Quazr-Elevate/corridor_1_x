"""From a seller's quote to a buyer's offer (build plan 06). Three records,
three audiences: the quote is the seller's and the desk's, the cost sheet is
the desk's alone, the offer is what the buyer sees. The purchase price lives
on the first two and never on the third.

Every price is an integer in the currency's minor unit, per ``unit``."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

SHEET_STATUSES = ("draft", "pending_approval", "ready", "published")
#: ``not_chosen``: the buyer went ahead with another offer on the deal (A-074).
OFFER_STATUSES = ("published", "expired", "withdrawn", "not_chosen")
#: The cost lines of a sheet, per unit, in the purchase currency.
COST_LINES = ("inland_freight", "ocean_freight", "insurance", "inspection", "documentation", "finance", "other")


class Quote(Base):
    """A matched seller's price for an RFQ. One per match; the seller may
    revise it until the desk builds a cost sheet on it."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("match_id", name="uq_quotes_match_id"),
        Index("ix_quotes_rfq", "rfq_id"),
        Index("ix_quotes_seller_time", "seller_business_id", text("created_at DESC")),
        CheckConstraint("price_minor > 0 AND quantity > 0 AND lead_time_days >= 0", name="ck_quotes_amounts"),
        CheckConstraint("length(currency) = 3", name="ck_quotes_currency"),
        CheckConstraint("unit IN ('MT', 'kg', 'quintal')", name="ck_quotes_unit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rfqs.id", ondelete="CASCADE", name="fk_quotes_rfq_id"), nullable=False
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rfq_matches.id", ondelete="CASCADE", name="fk_quotes_match_id"), nullable=False
    )
    seller_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_quotes_seller_business_id"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_quotes_created_by"), nullable=True
    )
    # What the seller asks: the purchase price. Never in a buyer response.
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    incoterm: Mapped[str] = mapped_column(String(3), nullable=False)
    port_of_loading: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_terms: Mapped[list] = mapped_column(JSON, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    # One row per required specification the buyer set a limit on:
    # [{"parameter_id", "meets", "value"}].
    specs: Mapped[list] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostSheet(Base):
    """The desk's working from a quote to a selling price (plan 6.3): costs
    per unit in the seller's currency, one FX conversion with the rate and
    buffer stored here, and the margin. Never leaves the desk."""

    __tablename__ = "cost_sheets"
    __table_args__ = (
        UniqueConstraint("quote_id", name="uq_cost_sheets_quote_id"),
        Index("ix_cost_sheets_deal", "deal_id"),
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in SHEET_STATUSES)})", name="ck_cost_sheets_status"),
        CheckConstraint(
            "purchase_price_minor > 0 AND sell_price_minor > 0 AND "
            + " AND ".join(f"{line}_minor >= 0" for line in COST_LINES),
            name="ck_cost_sheets_amounts",
        ),
        CheckConstraint("fx_rate > 0 AND fx_buffer_pct >= 0 AND margin_pct >= 0", name="ck_cost_sheets_rates"),
        # Nobody approves their own sheet (decision A-036).
        CheckConstraint(
            "approved_by IS NULL OR approved_by <> created_by", name="ck_cost_sheets_second_approver"
        ),
        CheckConstraint("(approved_by IS NULL) = (approved_at IS NULL)", name="ck_cost_sheets_approval_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="RESTRICT", name="fk_cost_sheets_quote_id"), nullable=False
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_cost_sheets_deal_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")

    # ─── Costs, per unit, in the purchase currency ─────────────────
    purchase_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    purchase_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inland_freight_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    ocean_freight_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # The day the freight was quoted; an old quote is refused (plan 6.3).
    freight_quoted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    insurance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    inspection_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    documentation_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    finance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    other_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # A line entered in another currency (CX-185): {line: {"amount_minor",
    # "currency", "rate", "as_of"}}, the rate being one unit of it in the
    # purchase currency, stored once. The ``<line>_minor`` above is always
    # the converted amount, rounded up. Lines in the purchase currency aren't listed.
    line_entries: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")

    # ─── The one FX conversion, stored (never looked up at render) ─
    deal_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    # 1 unit of the purchase currency in the deal currency, before the buffer.
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    fx_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    fx_buffer_pct: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2), nullable=False)

    # ─── Margin and the result ─────────────────────────────────────
    margin_pct: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2), nullable=False)
    # The floor in force when the sheet was last saved.
    min_margin_pct: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2), nullable=False)
    # The ceiling in force when the sheet was last saved (null on sheets saved before 0031).
    max_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(precision=6, scale=2), nullable=True)
    sell_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Why the sheet waits for a desk manager: under the floor, over the
    # ceiling, an old exchange rate. Empty when it is ready.
    approval_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_cost_sheets_created_by"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_cost_sheets_approved_by"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Offer(Base):
    """What the buyer is offered (plan 6.4): the selling price and the terms.
    It carries no cost, no margin and no purchase price."""

    __tablename__ = "offers"
    __table_args__ = (
        # One live offer per sheet; a withdrawn one can be followed by a corrected one (CX-186).
        Index(
            "uq_offers_cost_sheet_live", "cost_sheet_id", unique=True,
            sqlite_where=text("status <> 'withdrawn'"), postgresql_where=text("status <> 'withdrawn'"),
        ),
        Index("ix_offers_rfq", "rfq_id"),
        Index("ix_offers_buyer_time", "buyer_business_id", text("published_at DESC")),
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in OFFER_STATUSES)})", name="ck_offers_status"),
        CheckConstraint("price_minor > 0 AND quantity > 0", name="ck_offers_amounts"),
        CheckConstraint("specs_met >= 0 AND specs_met <= specs_total", name="ck_offers_specs"),
        CheckConstraint("buyer_business_id <> seller_business_id", name="ck_offers_two_parties"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_offers_deal_id"), nullable=False
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rfqs.id", ondelete="RESTRICT", name="fk_offers_rfq_id"), nullable=False
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="RESTRICT", name="fk_offers_quote_id"), nullable=False
    )
    cost_sheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cost_sheets.id", ondelete="RESTRICT", name="fk_offers_cost_sheet_id"), nullable=False
    )
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT", name="fk_offers_buyer_business_id"), nullable=False
    )
    seller_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT", name="fk_offers_seller_business_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="published", server_default="published")
    # The selling price per unit, in the deal currency.
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    incoterm: Mapped[str] = mapped_column(String(3), nullable=False)
    port_of_loading: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_terms: Mapped[list] = mapped_column(JSON, nullable=False)
    specs_met: Mapped[int] = mapped_column(Integer, nullable=False)
    specs_total: Mapped[int] = mapped_column(Integer, nullable=False)
    # At least two days before the quote behind it runs out (plan 6.4).
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_offers_published_by"), nullable=True
    )
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    # When the buyer was reminded the offer ends tomorrow: once per offer (CX-183).
    expiry_reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class OfferUnlock(Base):
    """A buyer paid OFFER_UNLOCK to see an offer's price and terms."""

    __tablename__ = "offer_unlocks"
    __table_args__ = (UniqueConstraint("offer_id", "buyer_business_id", name="uq_offer_unlocks_offer_buyer"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("offers.id", ondelete="CASCADE", name="fk_offer_unlocks_offer_id"), nullable=False
    )
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_offer_unlocks_buyer_business_id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_offer_unlocks_user_id"), nullable=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
