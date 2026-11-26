from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.shared.schemas import CamelModel, RequestModel, text


class ChooseOfferIn(RequestModel):
    offer_id: str


class MessageIn(RequestModel):
    body: text(2000, 1)  # type: ignore[valid-type]


class ChatMessageOut(CamelModel):
    id: str
    #: ``you`` (this side), ``counterparty`` (the other side, by code),
    #: ``corridor`` (the desk), ``system`` (an event line).
    author: Literal["you", "counterparty", "corridor", "system"]
    sender_code: str | None = None
    body: str
    #: ``held``: waiting for Corridor One X; ``rejected``: not passed on (see ``note``).
    status: Literal["delivered", "held", "rejected"]
    note: str | None = None
    created_at: datetime


class ChatOut(CamelModel):
    deal_code: str
    deal_status: str
    side: Literal["buyer", "seller"]
    #: The other side's company code.
    counterparty_code: str | None
    can_write: bool
    suspended: bool
    messages: list[ChatMessageOut]


class NegotiationStarted(CamelModel):
    deal_code: str
    deal_status: str
    chosen_offer_id: str


# ── Console ──────────────────────────────────────────────────────────


class DeskMessageOut(CamelModel):
    id: str
    origin: Literal["own", "relay", "desk", "system"]
    sender_code: str | None
    body: str
    status: str
    flags: list[str]
    note: str | None
    created_at: datetime


class DeskThreadOut(CamelModel):
    side: Literal["buyer", "seller"]
    company_code: str | None
    suspended: bool
    messages: list[DeskMessageOut]


class DeskChatOut(CamelModel):
    deal_code: str
    deal_status: str
    threads: list[DeskThreadOut]


class HeldMessageOut(CamelModel):
    id: str
    deal_code: str
    side: Literal["buyer", "seller"]
    sender_code: str | None
    body: str
    flags: list[str]
    created_at: datetime


class DeskMessageIn(RequestModel):
    body: text(2000, 1)  # type: ignore[valid-type]


class RejectMessageIn(RequestModel):
    reason: text(500, 10) = Field(...)  # type: ignore[valid-type]


class LiftSuspensionIn(RequestModel):
    reason: text(500, 10)  # type: ignore[valid-type]


# ── Counter-offers (CX-101) ──────────────────────────────────────────


class CounterIn(RequestModel):
    #: Per unit, in minor units of your own currency (the offer's for the
    #: buyer, your quote's for the seller).
    price_minor: int = Field(gt=0, le=10**13)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    note: text(500) | None = None  # type: ignore[valid-type]


class CounterOut(CamelModel):
    id: str
    #: True for your own counter-offers; false for the other side's, passed on by Corridor One X.
    mine: bool
    #: Per unit, in your own currency: your price, or what theirs means for you.
    price_minor: int
    currency: str
    quantity: Decimal | None
    note: str | None
    status: str
    #: Why Corridor One X didn't pass on your counter-offer.
    decision_note: str | None
    created_at: datetime


class CounterAnswerIn(RequestModel):
    accept: bool


class DeskCounterOut(CamelModel):
    id: str
    deal_code: str
    side: Literal["buyer", "seller"]
    price_minor: int
    currency: str
    implied_minor: int
    implied_currency: str
    margin_pct: Decimal
    sheet_margin_pct: Decimal | None = None
    min_margin_pct: Decimal | None = None
    max_margin_pct: Decimal | None = None
    quantity: Decimal | None
    note: str | None
    status: str
    decision_note: str | None
    created_at: datetime


class CounterRelayIn(RequestModel):
    #: Pass it on at another margin; omitted = the sheet's.
    margin_pct: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=2)


# ── Samples (CX-102) ─────────────────────────────────────────────────


class SampleHop(CamelModel):
    status: str
    at: datetime


class SampleOut(CamelModel):
    id: str
    status: str
    #: The seller's view: where to send it, while it is still to be sent.
    hub_address: str | None = None
    #: The seller's own courier reference (seller only).
    courier_ref: str | None = None
    #: Corridor One X's forward courier reference (buyer only, once forwarded).
    forward_courier_ref: str | None = None
    verdict: Literal["passed", "failed"] | None = None
    review_note: str | None = None
    hops: list[SampleHop]
    created_at: datetime


class DispatchIn(RequestModel):
    courier_ref: text(100, 4)  # type: ignore[valid-type]


class SampleReviewIn(RequestModel):
    verdict: Literal["passed", "failed"]
    note: text(500) | None = None  # type: ignore[valid-type]


class DeskSampleOut(CamelModel):
    id: str
    deal_code: str
    status: str
    seller_courier_ref: str | None
    retained_seal_no: str | None
    forward_seal_no: str | None
    forward_courier_ref: str | None
    verdict: str | None
    review_note: str | None
    hops: list[SampleHop]
    created_at: datetime


class SealIn(RequestModel):
    retained_seal_no: text(40, 4)  # type: ignore[valid-type]
    forward_seal_no: text(40, 4)  # type: ignore[valid-type]


class ForwardIn(RequestModel):
    courier_ref: text(100, 4)  # type: ignore[valid-type]
