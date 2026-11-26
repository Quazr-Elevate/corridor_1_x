from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, JSON, CheckConstraint, Enum, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, str_array


class BusinessStatus(str, enum.Enum):
    """Verification lifecycle of a business.

    draft                — signed up / filling the Passport
    pending_verification — "Send for verification" pressed; in the admin queue
    verified             — admin approved (listings visible, can reveal contacts)
    rejected             — admin rejected; ``verification_rejected_reason`` says why
    """

    draft = "draft"
    pending_verification = "pending_verification"
    verified = "verified"
    rejected = "rejected"


#: Allowed ``businesses.entity_type`` values.
ENTITY_TYPES = ("proprietorship", "partnership", "llp", "private_ltd", "public_ltd")


class Business(Base):
    """The company — the main entity. Verification, documents and listings
    belong to the business; ``users`` are the people who log in on its
    behalf. Its name and address are in the identity vault."""

    __tablename__ = "businesses"
    __table_args__ = (
        Index("uq_businesses_company_code", "company_code", unique=True),
        Index("ix_businesses_verification_queue", "verification_status", "verification_submitted_at"),
        CheckConstraint(
            "trade_position IS NULL OR trade_position IN ('seller', 'buyer', 'both')",
            name="ck_businesses_trade_position",
        ),
        CheckConstraint(
            "entity_type IS NULL OR entity_type IN "
            "('proprietorship', 'partnership', 'llp', 'private_ltd', 'public_ltd')",
            name="ck_businesses_entity_type",
        ),
        CheckConstraint("length(country) = 2", name="ck_businesses_country"),
        CheckConstraint(
            "verification_status <> 'verified' OR verified_at IS NOT NULL", name="ck_businesses_verified_has_date"
        ),
        CheckConstraint(
            "verification_status <> 'rejected' OR verification_rejected_reason IS NOT NULL",
            name="ck_businesses_rejected_has_reason",
        ),
        CheckConstraint(
            "(suspended_at IS NULL) = (suspended_reason IS NULL)", name="ck_businesses_suspension_has_reason"
        ),
        CheckConstraint(
            "verification_status = 'draft' OR verification_submitted_at IS NOT NULL",
            name="ck_businesses_submitted_has_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # ─── Company ───────────────────────────────────────────────
    # Shown wherever another party would see a name: ``{ISO2}-{6 digits}``,
    # issued at verification, never changed or reused (A-029). The name,
    # address and website live in ``business_identities``.
    company_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operating_countries: Mapped[list[str] | None] = mapped_column(str_array(CHAR(2)), nullable=True)

    # ─── Region (the street address is in the vault) ───────────
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(
        CHAR(2),
        ForeignKey("countries.code", ondelete="RESTRICT", name="fk_businesses_country"),
        nullable=False,
        default="IN",
        server_default="IN",
    )

    # ─── Branding (public images; shown on the dashboard hero) ─
    logo_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    banner_key: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # ─── How they trade ────────────────────────────────────────
    trade_position: Mapped[str | None] = mapped_column(String(10), nullable=True)
    seller_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    export_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_markets: Mapped[list[str] | None] = mapped_column(str_array(CHAR(2)), nullable=True)
    target_buyer_types: Mapped[list[str] | None] = mapped_column(str_array(String(40)), nullable=True)
    company_introduction: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Verification ──────────────────────────────────────────
    verification_status: Mapped[BusinessStatus] = mapped_column(
        Enum(BusinessStatus, name="business_status"),
        nullable=False,
        default=BusinessStatus.draft,
        server_default=BusinessStatus.draft.value,
    )
    verification_submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    verification_rejected_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Keys the admin ticked when rejecting — profile fields (``addressLine``)
    # and KYB entries (``kyb:gstin`` / ``doc:<entry id>``) — so the business
    # sees exactly what to fix. Cleared on resubmit and on approval.
    verification_rejected_items: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Set when the company is stopped from trading (three blocked chat
    # messages in 90 days, A-075). It can still read; a desk manager lifts it.
    suspended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None

    @property
    def is_verified(self) -> bool:
        return self.verification_status == BusinessStatus.verified and self.deleted_at is None
