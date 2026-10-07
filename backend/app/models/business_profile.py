from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class BusinessProfile(Base):
    """Business + bank details — one per user, filled during onboarding.

    Held separately from ``users`` and ``profiles`` because the KYB block is
    only relevant when the user actually wants to trade (payouts + trust).
    Field set roughly mirrors Tridge's company + business-profile sections.
    """

    __tablename__ = "business_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # ─── Company info (Onboarding step 1) ──────────────────────
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operating_countries: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(3)), nullable=True
    )
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ─── Business role / intent (Onboarding step 3) ────────────
    trade_position: Mapped[str | None] = mapped_column(String(40), nullable=True)
    seller_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    business_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    export_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_markets: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(3)), nullable=True
    )
    target_buyer_types: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(40)), nullable=True
    )
    main_objective: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_introduction: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Free-text metadata (kept from the earlier schema) ─────
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nature_of_business: Mapped[str | None] = mapped_column(String(200), nullable=True)
    udyam: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ─── Bank / payout ─────────────────────────────────────────
    bank_account_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_holder_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    ifsc_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Marks the moment the onboarding wizard was completed — the frontend
    # uses this to know whether to route new logins straight to the
    # dashboard or through /onboarding first.
    onboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="business_profile")
