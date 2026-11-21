"""Credits (build plan 17): one wallet per company, an append-only ledger
behind it, the free-RFQ quota, prices, plans and plan purchases. Separate
from the trade ledger of M5: credits pay for platform actions, never goods."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

#: Paid actions (plan 17.1). Each has a row in ``credit_prices``.
SPEND_TYPES = ("RFQ_POST", "OFFER_UNLOCK", "RFQ_VIEW", "LISTING_BOOST", "AI_QUERY", "SAMPLE_FEE")
#: What puts credits into a wallet.
TOP_UP_TYPES = ("PLAN_PURCHASE", "TOP_UP")
#: A correction is a new line, never an edit.
CORRECTION_TYPES = ("ADJUSTMENT", "REVERSAL")
#: Plan credits left when the plan ends are written off (A-051).
EXPIRY_TYPES = ("EXPIRY",)
ENTRY_TYPES = SPEND_TYPES + TOP_UP_TYPES + CORRECTION_TYPES + EXPIRY_TYPES

PURCHASE_STATUSES = ("created", "paid", "failed")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class CreditWallet(Base):
    """A company's credit balance. ``balance`` always equals the sum of the
    company's ledger lines; it is kept here so a spend is one guarded UPDATE."""

    __tablename__ = "credit_wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_credit_wallets_balance"),
        CheckConstraint("plan_credits >= 0", name="ck_credit_wallets_plan_credits"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_credit_wallets_business_id"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # The plan bought last and when it runs out. After the grace period the
    # company reads as on the Free plan.
    plan_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # How much of ``balance`` came from plans and runs out at ``plan_expires_at``
    # (A-051). Spends use these first; top-up credits don't expire.
    plan_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreditLedgerEntry(Base):
    """One line of the credit ledger. Insert only: no update, no delete."""

    __tablename__ = "credit_ledger"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_credit_ledger_idempotency"),
        Index("ix_credit_ledger_business_time", "business_id", text("created_at DESC")),
        CheckConstraint(_in("entry_type", ENTRY_TYPES), name="ck_credit_ledger_entry_type"),
        # A spend takes credits (or none, on the free quota); a top-up adds them.
        CheckConstraint(
            f"(NOT {_in('entry_type', SPEND_TYPES + EXPIRY_TYPES)} OR amount <= 0) AND "
            f"(NOT {_in('entry_type', TOP_UP_TYPES)} OR amount > 0)",
            name="ck_credit_ledger_sign",
        ),
        CheckConstraint("balance_after >= 0", name="ck_credit_ledger_balance_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_credit_ledger_business_id"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # True when a free-quota use covered a spend, so ``amount`` is 0.
    free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    # What the credits paid for or came from: ("rfq", id), ("purchase", id).
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # A retry with the same key finds this line instead of charging again.
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_credit_ledger_created_by"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class CreditFreeQuota(Base):
    """Free uses of a paid action, keyed on the company's registration number
    (its keyed hash), not on the account: deleting an account and signing up
    again with the same number finds the same row (plan 17.2)."""

    __tablename__ = "credit_free_quotas"
    __table_args__ = (
        UniqueConstraint("action", "registration_hash", name="uq_credit_free_quotas_registration"),
        CheckConstraint("used >= 0 AND used <= allowance", name="ck_credit_free_quotas_used"),
        CheckConstraint(_in("action", SPEND_TYPES), name="ck_credit_free_quotas_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    registration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # The business holding the number now; cleared when that business is erased.
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="SET NULL", name="fk_credit_free_quotas_business_id"), nullable=True
    )
    allowance: Mapped[int] = mapped_column(Integer, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class CreditPrice(Base):
    """What one paid action costs, in credits. Edited by an admin; values the
    client has not set yet are marked ``is_placeholder`` (A-031)."""

    __tablename__ = "credit_prices"
    __table_args__ = (
        CheckConstraint("credits >= 0", name="ck_credit_prices_credits"),
        CheckConstraint(_in("action", SPEND_TYPES), name="ck_credit_prices_action"),
    )

    action: Mapped[str] = mapped_column(String(20), primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreditPlan(Base):
    """Something a company can buy: a plan (credits plus a validity period)
    or a one-off top-up. ``price_minor`` is in the currency's minor unit."""

    __tablename__ = "credit_plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_credit_plans_code"),
        CheckConstraint("kind IN ('plan', 'top_up')", name="ck_credit_plans_kind"),
        CheckConstraint("credits > 0 AND price_minor >= 0", name="ck_credit_plans_amounts"),
        CheckConstraint("length(currency) = 3", name="ck_credit_plans_currency"),
        CheckConstraint(
            "(kind = 'plan' AND period_days > 0) OR (kind = 'top_up' AND period_days IS NULL)",
            name="ck_credit_plans_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PlanPurchase(Base):
    """One checkout. The plan's credits and price are copied in, so a later
    price change does not rewrite what was bought."""

    __tablename__ = "plan_purchases"
    __table_args__ = (
        UniqueConstraint("provider", "provider_order_id", name="uq_plan_purchases_order"),
        # Numbered from 1 in each Indian financial year (A-065): C1X/2026-27/0001.
        UniqueConstraint("invoice_fy", "invoice_number", name="uq_plan_purchases_invoice"),
        Index("ix_plan_purchases_business_time", "business_id", text("created_at DESC")),
        CheckConstraint(_in("status", PURCHASE_STATUSES), name="ck_plan_purchases_status"),
        CheckConstraint("status <> 'paid' OR paid_at IS NOT NULL", name="ck_plan_purchases_paid_has_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_plan_purchases_business_id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("credit_plans.id", ondelete="SET NULL", name="fk_plan_purchases_plan_id"), nullable=True
    )
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    plan_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="created", server_default="created")
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Sequential per paid purchase within ``invoice_fy`` ("2026-27"); the tax
    # invoice carries C1X/{invoice_fy}/{invoice_number:04d}.
    invoice_fy: Mapped[str | None] = mapped_column(String(7), nullable=True)
    invoice_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_plan_purchases_created_by"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class PaymentEvent(Base):
    """A webhook delivery from the payment processor. The unique event id is
    what makes a redelivery harmless."""

    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_payment_events_event"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("plan_purchases.id", ondelete="SET NULL", name="fk_payment_events_purchase_id"), nullable=True
    )
    # What we did with it: credited, failed, ignored, mismatch.
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class IdempotencyKey(Base):
    """The stored answer to a request that must not run twice (a checkout).
    A retry with the same key and body gets the same answer back."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("business_id", "route", "key", name="uq_idempotency_keys_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_idempotency_keys_business_id"), nullable=False
    )
    route: Mapped[str] = mapped_column(String(80), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class InvoiceCounter(Base):
    """The last invoice number issued in one financial year. Taken with a
    single UPDATE, so two payments at once never get the same number."""

    __tablename__ = "invoice_counters"
    __table_args__ = (CheckConstraint("last_number >= 0", name="ck_invoice_counters_last_number"),)

    fy: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
