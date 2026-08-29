from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Profile(Base):
    """Personal profile — every user has exactly one.

    Holds the person's name, contact info, address, and any public social /
    business URLs. Role-neutral: buyers and sellers both live here. Business
    identity (GSTIN, company, bank) lives in `business_profiles`.
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # ─── Primary ───────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ─── Address ───────────────────────────────────────────────
    address_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(CHAR(6), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, server_default="India")

    # ─── Additional contacts (OTP-verified when set) ───────────
    alt_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alt_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ─── Verification stamps ──────────────────────────────────
    # Written by the atomic /verify/* endpoints. A NULL stamp means the
    # paired value is either absent or unverified — the UI treats them the
    # same. Never mutate the value column without also setting/clearing its
    # stamp in the same commit.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alt_mobile_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alt_email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    business_email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Social / trust signals ────────────────────────────────
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    google_business_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ─── Consent (DPDP / PDPL trail) ──────────────────────────
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_version: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")
