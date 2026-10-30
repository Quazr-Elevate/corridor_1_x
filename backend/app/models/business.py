from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, Enum, Index, JSON, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base, UTCDateTime, str_array
from app.shared.normalize import normalize_legal_name, normalize_website


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
    """The company — the main entity. Verification, documents, listings and
    contact reveals belong to the business; ``users`` are the people who
    log in on its behalf."""

    __tablename__ = "businesses"
    __table_args__ = (
        Index(
            "uq_businesses_legal_name_normalized",
            "legal_name_normalized",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_businesses_website_normalized",
            "website_normalized",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
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
            "verification_status = 'draft' OR verification_submitted_at IS NOT NULL",
            name="ck_businesses_submitted_has_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # ─── Company identity ──────────────────────────────────────
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Canonical forms backing UNIQUE indexes — synced by the validators below.
    legal_name_normalized: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operating_countries: Mapped[list[str] | None] = mapped_column(str_array(CHAR(2)), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    website_normalized: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ─── Company address ───────────────────────────────────────
    address_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str] = mapped_column(CHAR(2), nullable=False, default="IN", server_default="IN")

    # ─── Social / trust signals ────────────────────────────────
    google_business_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

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
    # Camel-case keys the admin ticked when rejecting — e.g.
    # ``["fullName", "doc:business_registration"]``. Lets the trader see
    # exactly which fields or docs need to be fixed. Null for drafts
    # and verified rows; cleared on resubmit.
    verification_rejected_items: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @validates("legal_name")
    def _sync_legal_name(self, _key: str, value: str | None) -> str | None:
        self.legal_name_normalized = normalize_legal_name(value)
        return value

    @validates("website_url")
    def _sync_website(self, _key: str, value: str | None) -> str | None:
        self.website_normalized = normalize_website(value)
        return value

    @property
    def is_verified(self) -> bool:
        return self.verification_status == BusinessStatus.verified and self.deleted_at is None
