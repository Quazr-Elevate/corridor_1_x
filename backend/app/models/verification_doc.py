from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class DocStatus(str, enum.Enum):
    """Lifecycle of a single uploaded document.

    pending   — just uploaded, awaiting admin review
    approved  — admin accepted it
    rejected  — admin rejected it (user can re-upload a replacement)
    """

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class VerificationDoc(Base):
    """A KYB document uploaded by a user, tagged with its certificate type.

    One user can upload several (e.g. GST + FSSAI + IEC). Each doc has its
    own review lifecycle so admin can approve some and request a re-upload
    on others without rejecting the whole account.
    """

    __tablename__ = "verification_docs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-readable certificate name (e.g. "GST Certificate", "FSSAI License").
    # Free text — frontend presents a searchable list, but we don't lock it so
    # users can add things we haven't catalogued yet.
    cert_type: Mapped[str] = mapped_column(String(150), nullable=False)

    # User's original filename — shown in the admin queue alongside cert_type.
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    # On-disk path (relative to backend/uploads).
    stored_path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status"),
        nullable=False,
        default=DocStatus.pending,
    )
    # Only set when status=rejected — admin's note to the user so they know
    # what to fix on the re-upload.
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="verification_docs")
