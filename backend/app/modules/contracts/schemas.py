from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.shared.schemas import CamelModel, RequestModel, text


class DocumentOut(CamelModel):
    """A document as its own party reads it: the full text and its hash."""

    id: str
    kind: Literal["loi", "contract"]
    status: str
    body: str
    content_sha256: str
    value_minor: int
    currency: str
    expires_at: datetime
    void_reason: str | None
    issued_at: datetime
    you_signed_at: datetime | None
    corridor_signed_at: datetime | None
    effective_at: datetime | None


class SignIn(RequestModel):
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The role the signer states, e.g. "Director".
    signer_role: text(100, 2)  # type: ignore[valid-type]
    authority_confirmed: bool


class DeskSignature(CamelModel):
    signer_type: Literal["party", "corridor"]
    signer_role: str
    signed_at: datetime


class DeskDocumentOut(CamelModel):
    id: str
    deal_code: str
    kind: Literal["loi", "contract"]
    side: Literal["buyer", "seller"]
    status: str
    body: str
    content_sha256: str
    value_minor: int
    currency: str
    term_sheet_version: int
    template: str
    expires_at: datetime
    void_reason: str | None
    issued_at: datetime
    effective_at: datetime | None
    signatures: list[DeskSignature]


class VoidIn(RequestModel):
    reason: text(200, 10)  # type: ignore[valid-type]


class TemplateOut(CamelModel):
    id: str
    code: str
    version: int
    status: str
    body: str
    approval_note: str | None
    approved_at: datetime | None


class ApproveTemplateIn(RequestModel):
    #: The lawyer, their firm, and where the written approval is kept.
    note: text(500, 10)  # type: ignore[valid-type]


class ContractTermsIn(RequestModel):
    """One contract's own terms, on top of the agreed term sheet."""

    tolerance_pct: Decimal = Field(ge=0, le=10, max_digits=4, decimal_places=2)
    shipment_from: date
    shipment_to: date
    inspection_agency: text(100, 2)  # type: ignore[valid-type]
    inspection_point: text(100, 2)  # type: ignore[valid-type]
    late_penalty_pct: Decimal = Field(ge=0, le=20, max_digits=4, decimal_places=2)
    quality_penalty_pct: Decimal = Field(ge=0, le=20, max_digits=4, decimal_places=2)
    claim_window_days: int = Field(ge=1, le=365)
    governing_law: text(100, 2)  # type: ignore[valid-type]
    seat: text(100, 2)  # type: ignore[valid-type]
    force_majeure: text(300, 2)  # type: ignore[valid-type]
    #: Payment parameters, as the contract's payment terms need them (CX-110).
    advance_pct: int | None = Field(default=None, ge=1, le=99)
    tenor_days: int | None = Field(default=None, ge=1, le=365)
    credit_limit_minor: int | None = Field(default=None, gt=0, lt=10**15)
    credit_insurance_ref: text(100, 2) | None = None  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _window(self) -> ContractTermsIn:
        if self.shipment_to < self.shipment_from:
            raise ValueError("The shipment window must end on or after its start.")
        return self


class IssueContractsIn(RequestModel):
    sales: ContractTermsIn
    purchase: ContractTermsIn
    #: Who reviewed it, needed above the legal-review threshold (CX-109).
    legal_review_note: text(500, 10) | None = None  # type: ignore[valid-type]
