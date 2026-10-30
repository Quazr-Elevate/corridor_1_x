from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class KybInputKind(str, enum.Enum):
    """What the business must provide for a document type."""

    value = "value"                    # a number only (GSTIN, PAN)
    file = "file"                      # a certificate only (UAE trade licence)
    value_or_file = "value_or_file"    # either is accepted
    value_and_file = "value_and_file"  # both are required (FSSAI number + licence)


class KybDocumentType(Base):
    """Admin-managed list of KYB documents per country (the dropdown on the
    business profile). Hidden with ``active = false`` instead of deleted, so
    existing entries keep their label."""

    __tablename__ = "kyb_document_types"
    __table_args__ = (
        UniqueConstraint("country", "code", name="uq_kyb_document_types_country_code"),
        Index("ix_kyb_document_types_dropdown", "country", "active", "sort_order"),
        CheckConstraint("length(country) = 2", name="ck_kyb_document_types_country"),
        CheckConstraint("length(code) > 0", name="ck_kyb_document_types_code"),
        CheckConstraint("code NOT IN ('aadhaar', 'aadhar')", name="ck_kyb_document_types_no_aadhaar"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    country: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    # Stable slug, e.g. ``gstin`` — never shown to users.
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    input_kind: Mapped[KybInputKind] = mapped_column(Enum(KybInputKind, name="kyb_input_kind"), nullable=False)
    # Optional format check for the value (Python ``re`` full match).
    value_pattern: Mapped[str | None] = mapped_column(String(200), nullable=True)
    value_placeholder: Mapped[str | None] = mapped_column(String(60), nullable=True)
    help_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Must be present before the business can submit for KYB.
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # One value may belong to only one business (GSTIN, PAN, TRN…).
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def needs_value(self) -> bool:
        return self.input_kind in (KybInputKind.value, KybInputKind.value_and_file)

    @property
    def needs_file(self) -> bool:
        return self.input_kind in (KybInputKind.file, KybInputKind.value_and_file)
