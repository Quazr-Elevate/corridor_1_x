"""Quote, cost sheet and offer shapes. The purchase price, the costs and the
margin appear only in the seller's own quote and the desk's models. The
buyer's models have no field that could hold them."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.modules.catalog.schemas import Currency, Incoterm, Unit
from app.modules.rfq.schemas import PaymentTerms, Quantity
from app.shared.schemas import CamelModel, RequestModel, text

#: A price per unit in the currency's minor unit.
Minor = Annotated[int, Field(ge=0, le=10**13)]
PositiveMinor = Annotated[int, Field(gt=0, le=10**13)]
Percent = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)]


class SpecAnswer(RequestModel):
    """The seller's value for one of the buyer's required limits. Whether it
    meets the limit is worked out from the value, not taken from the seller
    (CX-180); ``meets`` is still accepted from older clients and ignored."""

    parameter_id: str
    value: text(200) | None = None  # type: ignore[valid-type]
    meets: bool | None = None


class QuoteIn(RequestModel):
    price_minor: PositiveMinor
    currency: Currency
    quantity: Quantity
    unit: Unit
    incoterm: Incoterm
    port_of_loading: text(100) | None = None  # type: ignore[valid-type]
    lead_time_days: int = Field(ge=0, le=730)
    payment_terms: list[PaymentTerms] = Field(min_length=1, max_length=5)
    #: Defaults to today plus the quote validity setting.
    valid_until: date | None = None
    specs: list[SpecAnswer] = Field(max_length=40)
    notes: text(2000) | None = None  # type: ignore[valid-type]


class SpecAnswerOut(CamelModel):
    parameter_id: str
    name: str
    meets: bool
    value: str | None


class QuoteRead(CamelModel):
    """The seller's own quote."""

    id: str
    rfq_id: str
    price_minor: int
    currency: str
    quantity: Decimal
    unit: str
    incoterm: str
    port_of_loading: str | None
    lead_time_days: int
    payment_terms: list[str]
    valid_until: date
    specs: list[SpecAnswerOut]
    notes: str | None
    #: False once the desk is working on it: the quote can no longer change.
    editable: bool
    updated_at: datetime


# ── Buyer ────────────────────────────────────────────────────────────


class OfferRead(CamelModel):
    """An offer as the buyer sees it. The first block is free to read; the
    second is null until the buyer unlocks the offer (decision A-042)."""

    id: str
    seller_code: str | None
    seller_state: str | None
    incoterm: str
    lead_time_days: int
    specs_met: int
    specs_total: int
    valid_until: date
    status: str
    unlocked: bool
    #: Credits unlocking costs; 0 once unlocked.
    unlock_cost: int

    price_minor: int | None = None
    currency: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    port_of_loading: str | None = None
    payment_terms: list[str] | None = None


class OfferList(CamelModel):
    total: int
    items: list[OfferRead]


# ── Desk ─────────────────────────────────────────────────────────────


class CostSheetIn(RequestModel):
    """Cost lines per unit, in the quote's currency, and the margin."""

    inland_freight_minor: Minor = 0
    ocean_freight_minor: Minor = 0
    freight_quoted_on: date | None = None
    insurance_minor: Minor = 0
    inspection_minor: Minor = 0
    documentation_minor: Minor = 0
    finance_minor: Minor = 0
    other_minor: Minor = 0
    margin_pct: Percent


class CostSheetRead(CamelModel):
    id: str
    quote_id: str
    status: str
    purchase_currency: str
    purchase_price_minor: int
    inland_freight_minor: int
    ocean_freight_minor: int
    freight_quoted_on: date | None
    insurance_minor: int
    inspection_minor: int
    documentation_minor: int
    finance_minor: int
    other_minor: int
    total_cost_minor: int
    deal_currency: str
    fx_rate: Decimal
    fx_as_of: date | None
    fx_buffer_pct: Decimal
    margin_pct: Decimal
    min_margin_pct: Decimal
    max_margin_pct: Decimal | None
    sell_price_minor: int
    needs_approval: bool
    #: What a desk manager has to accept: under the floor, over the ceiling, an old rate.
    approval_reasons: list[str] = []
    approved: bool


class DeskQuote(CamelModel):
    """A quote on the desk: the seller as a code, with its sheet and offer."""

    id: str
    seller_code: str | None
    seller_state: str | None
    price_minor: int
    currency: str
    quantity: Decimal
    unit: str
    incoterm: str
    port_of_loading: str | None
    lead_time_days: int
    payment_terms: list[str]
    valid_until: date
    specs: list[SpecAnswerOut]
    notes: str | None
    cost_sheet: CostSheetRead | None
    offer_id: str | None
    #: The seller quoted less than the buyer asked for (CX-184).
    part_quote: bool = False


class PublishIn(RequestModel):
    #: Defaults to the latest day allowed: two days before the quote runs out.
    valid_until: date | None = None


class OfferWithdrawn(CamelModel):
    id: str
    status: str


class PublishedOffer(CamelModel):
    id: str
    deal_code: str
    deal_status: str
    price_minor: int
    currency: str
    valid_until: date
