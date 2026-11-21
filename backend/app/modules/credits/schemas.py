"""Wallet, ledger, plan and purchase shapes. Nothing here names a person or
a company: the wallet is always the caller's own."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.credits import CreditLedgerEntry, CreditPlan, CreditPrice, PlanPurchase
from app.shared.schemas import CamelModel, RequestModel, text

SpendAction = Literal["RFQ_POST", "OFFER_UNLOCK", "RFQ_VIEW", "LISTING_BOOST", "AI_QUERY", "SAMPLE_FEE"]
PlanCode = text(40, 2)


class PriceRead(CamelModel):
    action: str
    credits: int
    #: True until the client sets the real price (plan 17.5).
    is_placeholder: bool


class PlanState(CamelModel):
    code: str
    name: str | None
    expires_at: datetime
    #: ``active`` until the expiry, then ``grace`` for PLAN_GRACE_DAYS.
    state: Literal["active", "grace"]


class FreeQuotaRead(CamelModel):
    allowance: int
    used: int
    remaining: int


class WalletRead(CamelModel):
    balance: int
    #: How much of the balance comes from the plan and ends with it (A-051).
    plan_credits: int = 0
    #: None on the Free plan (never bought one, or lapsed past the grace period).
    plan: PlanState | None
    #: Free RFQs of this company; None until it is verified.
    free_rfqs: FreeQuotaRead | None
    prices: list[PriceRead]
    #: False when no payment processor is set up, so the buy buttons can say so.
    checkout_available: bool


class LedgerLine(CamelModel):
    id: str
    entry_type: str
    amount: int
    balance_after: int
    free: bool
    reference_type: str | None
    reference_id: str | None
    note: str | None
    created_at: datetime


class LedgerPage(CamelModel):
    total: int
    items: list[LedgerLine]


class PlanRead(CamelModel):
    code: str
    name: str
    kind: Literal["plan", "top_up"]
    credits: int
    price_minor: int
    currency: str
    period_days: int | None
    is_placeholder: bool


class PurchaseCreate(RequestModel):
    plan_code: PlanCode  # type: ignore[valid-type]


class PurchaseRead(CamelModel):
    id: str
    plan_code: str
    credits: int
    amount_minor: int
    currency: str
    status: Literal["created", "paid", "failed"]
    provider: str
    #: What the browser checkout opens with.
    provider_order_id: str
    checkout_key: str
    #: The tax invoice number once paid: C1X/2026-27/0001 (A-065).
    invoice_ref: str | None = None


class WebhookAck(CamelModel):
    received: bool = True


# ── Admin ────────────────────────────────────────────────────────────


class PriceUpdate(RequestModel):
    credits: int = Field(ge=0, le=10_000)


class AdminPlanRead(PlanRead):
    active: bool


class PlanUpdate(RequestModel):
    name: text(80, 2) | None = None  # type: ignore[valid-type]
    credits: int | None = Field(default=None, gt=0, le=1_000_000)
    price_minor: int | None = Field(default=None, ge=0, le=1_000_000_000)
    period_days: int | None = Field(default=None, gt=0, le=3660)
    active: bool | None = None


def price_to_read(p: CreditPrice) -> PriceRead:
    return PriceRead(action=p.action, credits=p.credits, is_placeholder=p.is_placeholder)


def line_to_read(e: CreditLedgerEntry) -> LedgerLine:
    return LedgerLine(
        id=str(e.id), entry_type=e.entry_type, amount=e.amount, balance_after=e.balance_after, free=e.free,
        reference_type=e.reference_type, reference_id=e.reference_id, note=e.note, created_at=e.created_at,
    )


def plan_to_read(p: CreditPlan) -> PlanRead:
    return PlanRead(
        code=p.code, name=p.name, kind=p.kind, credits=p.credits, price_minor=p.price_minor, currency=p.currency,
        period_days=p.period_days, is_placeholder=p.is_placeholder,
    )


def admin_plan_to_read(p: CreditPlan) -> AdminPlanRead:
    return AdminPlanRead(**plan_to_read(p).model_dump(), active=p.active)


def purchase_to_read(p: PlanPurchase, checkout_key: str) -> PurchaseRead:
    return PurchaseRead(
        id=str(p.id), plan_code=p.plan_code, credits=p.credits, amount_minor=p.amount_minor, currency=p.currency,
        status=p.status, provider=p.provider, provider_order_id=p.provider_order_id, checkout_key=checkout_key,
        invoice_ref=f"C1X/{p.invoice_fy}/{p.invoice_number:04d}" if p.invoice_fy and p.invoice_number else None,
    )
