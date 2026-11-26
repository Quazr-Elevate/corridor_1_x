from __future__ import annotations

from datetime import datetime
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
