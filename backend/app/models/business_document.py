from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime

if TYPE_CHECKING:
    from app.models.kyb_document_type import KybDocumentType


class DocStatus(str, enum.Enum):
    """pending → admin approves / rejects (the business can correct it)."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


_FILE_COLS = ("original_filename", "storage_key", "mime_type", "size_bytes")
_VALUE_COLS = ("value_encrypted", "value_key_version", "value_hash", "value_last4")


def _all_or_none(cols: tuple[str, ...]) -> str:
    return f"({' AND '.join(f'{c} IS NULL' for c in cols)}) OR ({' AND '.join(f'{c} IS NOT NULL' for c in cols)})"


class BusinessDocument(Base):
    """One KYB entry of a business: a document type (from the admin's
    per-country list, or "Other" with a custom name) plus a value, a file,
    or both.

    The value (GSTIN, PAN, IEC…) is never stored in plain text:
    ``value_encrypted`` holds AES-256-GCM ciphertext, ``value_hash`` a keyed
    hash for duplicate checks, ``value_last4`` the masked hint. Files live in
    private storage and are served only to users of the owning business and
    to admins (every admin view is audited).
    """

    __tablename__ = "business_documents"
    __table_args__ = (
        Index("ix_business_documents_business", "business_id", text("uploaded_at DESC")),
        Index(
            "ix_business_documents_pending",
            "uploaded_at",
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_business_documents_uploaded_by", "uploaded_by_user_id"),
        # One entry per admin-defined type per business ("Other" may repeat).
        Index(
            "uq_business_documents_business_type",
            "business_id",
            "document_type_id",
            unique=True,
            sqlite_where=text("document_type_id IS NOT NULL"),
            postgresql_where=text("document_type_id IS NOT NULL"),
        ),
        # A unique-type value (GSTIN, PAN…) belongs to one business only;
        # rejected entries don't block the real owner.
        Index(
            "uq_business_documents_unique_value",
            "document_type_id",
            "value_hash",
            unique=True,
            sqlite_where=text("value_unique AND value_hash IS NOT NULL AND status <> 'rejected'"),
            postgresql_where=text("value_unique AND value_hash IS NOT NULL AND status <> 'rejected'"),
        ),
        CheckConstraint(
            "value_encrypted IS NOT NULL OR storage_key IS NOT NULL", name="ck_business_documents_has_content"
        ),
        CheckConstraint(_all_or_none(_FILE_COLS), name="ck_business_documents_file_complete"),
        CheckConstraint(_all_or_none(_VALUE_COLS), name="ck_business_documents_value_complete"),
        CheckConstraint(
            "size_bytes IS NULL OR (size_bytes > 0 AND size_bytes <= 10485760)", name="ck_business_documents_size"
        ),
        CheckConstraint("length(doc_type) > 0", name="ck_business_documents_doc_type"),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL", name="ck_business_documents_rejected_reason"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_business_documents_business_id"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_business_documents_uploaded_by_user_id"), nullable=True
    )
    # Null = "Other" (custom name in ``doc_type``).
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("kyb_document_types.id", ondelete="RESTRICT", name="fk_business_documents_document_type_id"),
        nullable=True,
    )
    # Display name: the type's name, or the custom name typed for "Other".
    doc_type: Mapped[str] = mapped_column(String(150), nullable=False)

    # ── Value (encrypted) ────────────────────────────────────────────
    value_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_key_version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    value_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    value_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # Copied from the type's ``is_unique`` when the value is saved, so the
    # database can enforce one-business-per-value with a partial index.
    value_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    # ── File (optional) ──────────────────────────────────────────────
    # Uploader's filename (sanitised) — display only.
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Full key in private storage, e.g. ``verification/<business_id>/<hex>.pdf``.
    storage_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Detected from the file bytes (PDF/JPEG/PNG/WEBP).
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Review ───────────────────────────────────────────────────────
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status"), nullable=False, default=DocStatus.pending, server_default=DocStatus.pending.value
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)  # admin email
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document_type: Mapped[KybDocumentType | None] = relationship(lazy="joined")

    @property
    def has_value(self) -> bool:
        return self.value_encrypted is not None

    @property
    def has_file(self) -> bool:
        return self.storage_key is not None
