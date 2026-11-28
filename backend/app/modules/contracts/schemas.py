from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

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
