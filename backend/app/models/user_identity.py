from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base, UTCDateTime
from app.shared.normalize import normalize_phone

#: Columns that name or reach a person. Nothing outside
#: ``app/modules/masking`` reads this table (tests/test_masking.py).
PERSON_COLUMNS = ("full_name", "email", "phone")


class UserIdentity(Base):
    """The identity vault row of a trader (CX-149, A-028, A-070): their name,
    work email (the sign-in handle) and phone. ``users`` holds the account:
    role, password, lockout and sessions. The row is deleted, not
    anonymised, when the account is deleted, so the email can sign up again."""

    __tablename__ = "user_identities"
    __table_args__ = (
        Index("uq_user_identities_email", "email", unique=True),
        Index("uq_user_identities_phone_normalized", "phone_normalized", unique=True),
        CheckConstraint("email = lower(email)", name="ck_user_identities_email_lowercase"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE", name="fk_user_identities_user_id"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Work email — the sign-in handle. Stored lowercased.
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Canonical phone (digits + '+') backing the UNIQUE index; synced below.
    phone_normalized: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @validates("phone")
    def _sync_phone(self, _key: str, value: str | None) -> str | None:
        self.phone_normalized = normalize_phone(value)
        return value
