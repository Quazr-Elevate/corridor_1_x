from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class DocStatus(str, enum.Enum):
    """pending → admin approves / rejects (the business can re-upload)."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class BusinessDocument(Base):
    """A KYB file (GST certificate, FSSAI licence, IEC…) of a business.

    Served only to users of the owning business and to admins.
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
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_business_documents_size"),
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
    # When this upload fills a known country-mandated slot
    # (business_document_requirements.id); NULL for custom uploads that
    # don't match any catalog entry. ON DELETE SET NULL so retiring a
    # requirement leaves the file intact as a "custom" doc.
    required_doc_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "business_document_requirements.id",
            ondelete="SET NULL",
            name="fk_business_documents_required_doc_type_id",
        ),
        nullable=True,
    )
    # Free text — the UI offers a searchable list ("GST Certificate", "IEC"…).
    doc_type: Mapped[str] = mapped_column(String(150), nullable=False)
    # Uploader's filename (sanitised) — display only.
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    # Full key in storage, e.g. ``verification/<business_id>/<hex>.pdf``.
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    # Detected from the file bytes (PDF/JPEG/PNG/WEBP).
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status"), nullable=False, default=DocStatus.pending, server_default=DocStatus.pending.value
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)  # admin email
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
