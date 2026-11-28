"""RFQ shapes. Three audiences, three models: the buyer sees their own RFQ
in full, a matched seller sees it without the buyer's price or name, and
the desk sees everything with company codes in place of names."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from app.modules.catalog.schemas import Category, Currency, Incoterm, Operator, Unit
from app.shared.schemas import CamelModel, CountryCode, RequestModel, text

PaymentTerms = Literal["advance", "lc_sight", "lc_usance", "advance_balance_docs", "open_account"]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
#: A price per unit in the currency's minor unit (paise, fils, cents).
PriceMinor = Annotated[int, Field(ge=0, le=10**13)]


class SpecLimit(RequestModel):
    """The buyer's limit for one row of the category template."""

    parameter_id: str
    value: text(200, 1)  # type: ignore[valid-type]
    operator: Operator | None = None  # defaults to the parameter's


class RfqCreate(RequestModel):
    """A draft needs only what it is about; the rest is checked on submit."""

    kind: Literal["listing", "open"]
    listing_id: str | None = None
    category: Category | None = None  # taken from the listing when kind = listing
    product_name: text(200, 2) | None = None  # type: ignore[valid-type]
    variety: text(100) | None = None  # type: ignore[valid-type]
    grade: text(100) | None = None  # type: ignore[valid-type]
    specs: list[SpecLimit] | None = Field(default=None, max_length=40)
    quantity: Quantity | None = None
    unit: Unit | None = None
    packaging: text(50) | None = None  # type: ignore[valid-type]
    certificate_type_ids: list[str] | None = Field(default=None, max_length=20)
    target_price_min: PriceMinor | None = None
    target_price_max: PriceMinor | None = None
    currency: Currency | None = None
    incoterms: list[Incoterm] | None = Field(default=None, max_length=6)
    payment_terms: PaymentTerms | None = None
    delivery_country: CountryCode | None = None
    destination_port: text(100) | None = None  # type: ignore[valid-type]
    delivery_from: date | None = None
    delivery_to: date | None = None
    notes: text(2000) | None = None  # type: ignore[valid-type]


class RfqUpdate(RequestModel):
    """Any subset of a draft's fields. ``kind`` and the listing are fixed."""

    category: Category | None = None
    product_name: text(200, 2) | None = None  # type: ignore[valid-type]
    variety: text(100) | None = None  # type: ignore[valid-type]
    grade: text(100) | None = None  # type: ignore[valid-type]
    specs: list[SpecLimit] | None = Field(default=None, max_length=40)
    quantity: Quantity | None = None
    unit: Unit | None = None
    packaging: text(50) | None = None  # type: ignore[valid-type]
    certificate_type_ids: list[str] | None = Field(default=None, max_length=20)
    target_price_min: PriceMinor | None = None
    target_price_max: PriceMinor | None = None
    currency: Currency | None = None
    incoterms: list[Incoterm] | None = Field(default=None, max_length=6)
    payment_terms: PaymentTerms | None = None
    delivery_country: CountryCode | None = None
    destination_port: text(100) | None = None  # type: ignore[valid-type]
    delivery_from: date | None = None
    delivery_to: date | None = None
    notes: text(2000) | None = None  # type: ignore[valid-type]


class SpecLimitOut(CamelModel):
    parameter_id: str
    code: str
    name: str
    unit: str | None = None
    value: str
    operator: str


class CertificateNeed(CamelModel):
    certificate_type_id: str
    name: str


class RfqSellerView(CamelModel):
    """What a matched seller reads, and what the buyer's preview shows. No
    target price and no buyer name: only the buyer's code and country."""

    id: str
    deal_code: str | None
    buyer_code: str | None
    buyer_country: str | None
    category: str
    product_name: str
    variety: str | None
    grade: str | None
    specs: list[SpecLimitOut]
    quantity: Decimal | None
    unit: str
    packaging: str | None
    certificates: list[CertificateNeed]
    incoterms: list[str]
    payment_terms: str | None
    delivery_country: str | None
    destination_port: str | None
    delivery_from: date | None
    delivery_to: date | None
    notes: str | None
    expires_at: datetime | None


class RfqRead(RfqSellerView):
    """The buyer's own RFQ."""

    kind: str
    listing_id: str | None
    status: str
    #: ``awaiting`` the desk or sellers, ``quoted``, ``expired``, or the RFQ's own status.
    tracking: str
    target_price_min: int | None
    target_price_max: int | None
    currency: str | None
    #: What is still needed before it can be submitted.
    missing: list[str]
    #: Shown when the desk refused it.
    rejection_reason: str | None
    submitted_at: datetime | None
    created_at: datetime


class RfqList(CamelModel):
    total: int
    items: list[RfqRead]


class SubmitCost(CamelModel):
    """What submitting will take, so the button can print it first."""

    credits: int
    free: bool


class MatchedRfqRow(CamelModel):
    """An RFQ in a seller's inbox before they open it: enough to decide."""

    id: str
    category: str
    product_name: str
    quantity: Decimal | None
    unit: str
    delivery_country: str | None
    delivery_to: date | None
    expires_at: datetime | None
    #: False until the seller has paid to open it.
    opened: bool
    #: Credits the first opening costs.
    open_cost: int
    matched_at: datetime | None


class MatchedRfqList(CamelModel):
    total: int
    items: list[MatchedRfqRow]


# ── Desk ─────────────────────────────────────────────────────────────


class MatchReason(CamelModel):
    rule: str
    ok: bool
    detail: str


class MatchOut(CamelModel):
    id: str
    seller_code: str | None
    seller_state: str | None
    listing_id: str | None
    listing_name: str | None
    status: str
    source: str
    reasons: list[MatchReason]
    #: 0–100 from the ranking (CX-177); null for a seller the desk added.
    score: int | None = None
    #: {specs|price|response: {points, of, detail}}
    score_parts: dict | None = None
    viewed_at: datetime | None


class DeskRfqRow(CamelModel):
    id: str
    deal_code: str | None
    buyer_code: str | None
    category: str
    product_name: str
    quantity: Decimal | None
    unit: str
    delivery_country: str | None
    status: str
    submitted_at: datetime | None
    expires_at: datetime | None
    proposed: int
    confirmed: int


class DeskRfqList(CamelModel):
    total: int
    items: list[DeskRfqRow]


class DeskLeakFlag(CamelModel):
    field: str
    reasons: list[str]


class DeskRfqDetail(CamelModel):
    rfq: RfqSellerView
    kind: str
    status: str
    target_price_min: int | None
    target_price_max: int | None
    currency: str | None
    #: Why it is held, or why it was rejected.
    desk_reason: str | None
    submitted_at: datetime | None
    matches: list[MatchOut]
    leak_flags: list[DeskLeakFlag]


class DeskStatus(CamelModel):
    id: str
    status: str
    deal_status: str | None


class DeskReasonIn(RequestModel):
    reason: text(500, 5)  # type: ignore[valid-type]


class MatchAdd(RequestModel):
    listing_id: str


class HeldCountryIn(RequestModel):
    reason: text(200, 5)  # type: ignore[valid-type]


class HeldCountryOut(CamelModel):
    code: str
    reason: str


class TradeSettingOut(CamelModel):
    key: str
    value: Decimal
    is_placeholder: bool


class TradeSettingIn(RequestModel):
    value: Decimal = Field(ge=0, le=100000, max_digits=12, decimal_places=4)
