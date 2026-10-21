"""One-time 6-digit codes sent to an inbox.

Keyed by email (no FK) because at signup the user does not exist yet.
Only the SHA-256 (HMAC with a server secret) of the code is stored.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, Enum, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class EmailCodePurpose(str, enum.Enum):
    signup = "signup"
    reset_password = "reset_password"  # future
    invite = "invite"  # future


class EmailCode(Base):
    __tablename__ = "email_codes"
    __table_args__ = (
        Index("ix_email_codes_lookup", "email", "purpose", text("created_at DESC")),
        Index("ix_email_codes_expires_at", "expires_at"),
        CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_email_codes_attempts"),
        CheckConstraint("consumed_at IS NULL OR verified_at IS NOT NULL", name="ck_email_codes_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[EmailCodePurpose] = mapped_column(Enum(EmailCodePurpose, name="email_code_purpose"), nullable=False)
    code_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    # Dead after 5 wrong tries.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # Correct code entered — gates account creation (for 30 minutes).
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Account created with it — single use.
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
