from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, Boolean, CheckConstraint, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime
from app.models.exchange_rate import SUPPORTED_CURRENCIES


class Country(Base):
    """A country Corridor One X onboards businesses from.

    Created by an admin **together with** its KYB documents (at least one
    required) — see ``POST /admin/kyb/countries``. Offered to businesses
    while ``active`` and it has an active required document. Never deleted
    (businesses and document types reference it): ``active = false`` pauses
    new onboarding; businesses already there keep working.
    """

    __tablename__ = "countries"
    __table_args__ = (
        Index("ix_countries_active", "active"),
        Index("uq_countries_name", "name", unique=True),
        CheckConstraint("length(code) = 2 AND code = upper(code)", name="ck_countries_code"),
        CheckConstraint("length(trim(name)) >= 2", name="ck_countries_name"),
        CheckConstraint("dial_code IS NULL OR dial_code LIKE '+%'", name="ck_countries_dial_code"),
        CheckConstraint(
            "default_currency IN (" + ", ".join(f"'{c}'" for c in SUPPORTED_CURRENCIES) + ")",
            name="ck_countries_default_currency",
        ),
    )

    code: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    flag: Mapped[str | None] = mapped_column(String(8), nullable=True)
    dial_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    # A new user's display currency (business country → INR / AED / USD).
    default_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="USD", server_default="USD")
    # Address form labels: "State" / "Emirate"; "PIN code" / "PO Box".
    region_label: Mapped[str] = mapped_column(
        String(30), nullable=False, default="State / region", server_default="State / region"
    )
    postal_label: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Postal code", server_default="Postal code"
    )
    # Optional format check for the postcode (Python ``re`` full match).
    postal_pattern: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Open for onboarding. False = paused (existing businesses unaffected).
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
