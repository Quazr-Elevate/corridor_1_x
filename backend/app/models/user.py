from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, Enum, ForeignKey, Index, Integer, String, Uuid, event, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base, UTCDateTime
from app.models.business import Business
from app.models.exchange_rate import SUPPORTED_CURRENCIES
from app.shared.normalize import normalize_phone


class UserRole(str, enum.Enum):
    """What the person may do in the app (permissions). Only ``owner`` is
    used today; ``admin``/``member`` arrive with team invites."""

    owner = "owner"
    admin = "admin"
    member = "member"


class AccountStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base):
    """A person who logs in and belongs to exactly one business.

    Created at signup only after the work email was proven with a 6-digit
    code (``email_codes``), so ``email_verified_at`` and ``password_hash``
    are always set.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email", "email", unique=True),
        Index(
            "uq_users_phone_normalized",
            "phone_normalized",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_one_owner_per_business",
            "business_id",
            unique=True,
            sqlite_where=text("role = 'owner' AND deleted_at IS NULL"),
            postgresql_where=text("role = 'owner' AND deleted_at IS NULL"),
        ),
        Index("ix_users_business_id", "business_id"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint("session_version >= 0", name="ck_users_session_version"),
        CheckConstraint(
            "display_currency IN (" + ", ".join(f"'{c}'" for c in SUPPORTED_CURRENCIES) + ")",
            name="ck_users_display_currency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT", name="fk_users_business_id"), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.owner, server_default=UserRole.owner.value
    )

    # Work email — the login handle. Stored lowercased.
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"),
        nullable=False,
        default=AccountStatus.active,
        server_default=AccountStatus.active.value,
    )
    email_verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    # ─── Person ────────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Job title (display only) — unlike ``role`` it grants nothing.
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Canonical phone (digits + '+') backing a UNIQUE index; synced below.
    phone_normalized: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Bumped to revoke every outstanding session cookie (password change,
    # logout-everywhere, account deletion). Embedded in the cookie as "sv".
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ─── Consent (DPDP / PDPL trail) ──────────────────────────
    consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Currency the user sees converted prices and types filter amounts in.
    # Defaults from the business country (see default_display_currency).
    display_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="USD")

    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Soft delete (DPDP erasure; email anonymised).
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # Many-to-one, always loaded with the user (one JOIN) so services can
    # read ``user.business`` without async lazy loads.
    business: Mapped[Business] = relationship(lazy="joined", innerjoin=True)

    @validates("phone")
    def _sync_phone(self, _key: str, value: str | None) -> str | None:
        self.phone_normalized = normalize_phone(value)
        return value


#: Business country → default display currency (everything else: USD).
COUNTRY_CURRENCY = {"IN": "INR", "AE": "AED"}


def default_display_currency(country: str | None) -> str:
    return COUNTRY_CURRENCY.get((country or "").strip().upper(), "USD")


@event.listens_for(User, "before_insert")
def _default_display_currency(_mapper, _conn, target: User) -> None:
    """New users without an explicit choice get their business country's
    currency (IN → INR, AE → AED, else USD)."""
    if not target.display_currency:
        business = target.__dict__.get("business")
        target.display_currency = default_display_currency(business.country if business is not None else None)
