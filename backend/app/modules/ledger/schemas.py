from __future__ import annotations

from datetime import datetime

from app.shared.schemas import CamelModel, RequestModel, text


class EntryOut(CamelModel):
    account: str
    leg: str | None
    #: Debit positive, credit negative, in minor units.
    amount_minor: int
    currency: str


class TransactionOut(CamelModel):
    id: str
    kind: str
    memo: str
    reverses_id: str | None
    reversed: bool
    reference_type: str | None
    reference_id: str | None
    created_at: datetime
    entries: list[EntryOut]


class LegOut(CamelModel):
    leg: str
    #: account → currency → balance in minor units.
    balances: dict[str, dict[str, int]]


class DealBooksOut(CamelModel):
    deal_code: str
    legs: list[LegOut]
    #: Per currency; always zero when the books are sound.
    totals: dict[str, int]
    balanced: bool
    transactions: list[TransactionOut]


class ReverseIn(RequestModel):
    reason: text(300, 10)  # type: ignore[valid-type]
