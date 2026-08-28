from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class OnboardingPath(str, enum.Enum):
    """Which document the business was first identified with."""

    gstin = "gstin"
    pan = "pan"


class BusinessProfile(Base):
    """Business identity — optional, one per user.

    Any user (buyer or seller) can add a business profile for credibility.
    Sellers additionally need bank details filled here before admin will
    flip their `users.status` to `verified` (payout target).

    Personal fields (name, address, alt contacts, social URLs) belong to
    `profiles` and are NOT duplicated here.
    """

    __tablename__ = "business_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # ─── Business identity ─────────────────────────────────────
    onboarding_path: Mapped[OnboardingPath] = mapped_column(
        Enum(OnboardingPath, name="business_onboarding_path"), nullable=False
    )
    # Partial-unique index (WHERE gstin IS NOT NULL) added in migration.
    gstin: Mapped[str | None] = mapped_column(CHAR(15), nullable=True)
    pan: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nature_of_business: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ─── Regulatory extras ─────────────────────────────────────
    udyam: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhaar: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ─── Bank / payout (merged from ex-`bank_details` table) ───
    # Nullable so a business can exist without bank; enforced at
    # verification time (`users.status = verified` requires all filled).
    bank_account_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_holder_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="business_profile")
