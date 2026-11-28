from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.shared.schemas import CamelModel, RequestModel, text

Currency = Literal["INR", "AED", "USD"]


class BankAccountIn(RequestModel):
    currency: Currency
    country: Literal["IN", "AE"]
    bank_name: text(100, 2)  # type: ignore[valid-type]
    #: IFSC in India, SWIFT/BIC elsewhere.
    routing_code: text(20, 8)  # type: ignore[valid-type]
    account_number: text(40, 6)  # type: ignore[valid-type]
    holder_name: text(150, 2)  # type: ignore[valid-type]


class BankAccountOut(CamelModel):
    """An account as its own business sees it: masked."""

    id: str
    currency: str
    country: str
    bank_name: str
    routing_code: str
    account_masked: str
    status: str
    rejected_reason: str | None
    created_at: datetime


class DeskBankAccountOut(BankAccountOut):
    company_code: str | None
    verified_at: datetime | None
    cooling_off_until: datetime | None


class RevealedAccount(CamelModel):
    id: str
    account_number: str
    holder_name: str


class NoteIn(RequestModel):
    note: text(300, 5)  # type: ignore[valid-type]


class StatementMapIn(RequestModel):
    name: text(100, 2)  # type: ignore[valid-type]
    #: The statement's header for each: date, amount, reference, payer_account, and optionally currency.
    columns: dict[str, str] = Field(max_length=8)
    date_format: text(20, 2)  # type: ignore[valid-type]
    default_currency: Currency


class StatementMapOut(CamelModel):
    id: str
    name: str
    columns: dict[str, str]
    date_format: str
    default_currency: str


class ImportOut(CamelModel):
    statement_id: str
    lines_total: int
    lines_new: int
    lines_matched: int
    debits_skipped: int


class StatementLineOut(CamelModel):
    id: str
    booked_on: date
    amount_minor: int
    currency: str
    reference: str
    payer_account_last4: str | None
    status: str
    note: str | None


class MatchIn(RequestModel):
    milestone_id: str
    note: text(300, 5)  # type: ignore[valid-type]
