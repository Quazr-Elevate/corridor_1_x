from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base, UTCDateTime
from app.shared.normalize import normalize_legal_name, normalize_website

#: Columns that name or locate a company. Nothing outside
#: ``app/modules/masking`` reads this table (tests/test_masking.py).
VAULT_COLUMNS = (
    "legal_name",
    "website_url",
    "address_line",
    "city",
    "pincode",
    "google_business_url",
    "facebook_url",
)


class BusinessIdentity(Base):
    """The identity vault row of a business (build plan 18.1): who the company
    is and where it sits. The rest of the app holds ``businesses.company_code``.
    The row is deleted, not soft-deleted, when the business is erased."""

    __tablename__ = "business_identities"
    __table_args__ = (
        Index("uq_business_identities_legal_name_normalized", "legal_name_normalized", unique=True),
        Index("uq_business_identities_website_normalized", "website_normalized", unique=True),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE", name="fk_business_identities_business_id"),
        primary_key=True,
    )
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Canonical forms backing the UNIQUE indexes — synced by the validators below.
    legal_name_normalized: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    website_normalized: Mapped[str | None] = mapped_column(String(300), nullable=True)
    address_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    google_business_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @validates("legal_name")
    def _sync_legal_name(self, _key: str, value: str | None) -> str | None:
        self.legal_name_normalized = normalize_legal_name(value)
        return value

    @validates("website_url")
    def _sync_website(self, _key: str, value: str | None) -> str | None:
        self.website_normalized = normalize_website(value)
        return value
