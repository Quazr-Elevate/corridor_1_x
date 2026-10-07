from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.business_profile import BusinessProfile
    from app.models.profile import Profile
    from app.models.verification_doc import VerificationDoc


class UserStatus(str, enum.Enum):
    """Onboarding + verification funnel.

    signed_up            — account row exists, email not yet verified
    email_verified       — link clicked; user is prompted to set a password
    active               — password set; can log in but hasn't filled all 7
                           mandatory profile fields for the Verified badge
    pending_verification — all 7 mandatory fields are filled; admin has not
                           yet decided. The user sits in the admin queue.
    verified             — admin approved the business (badge visible)
    rejected             — admin rejected; a reason is stored and shown
    """

    signed_up = "signed_up"
    email_verified = "email_verified"
    active = "active"
    pending_verification = "pending_verification"
    verified = "verified"
    rejected = "rejected"


class User(Base):
    """Auth account.

    Signup captures work email + business name. A verification link is sent
    to the email; clicking it flips ``email_verified_at``. The user then sets
    a password (populates ``password_hash``) and can log in.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Work email — the login handle. Stored lowercased; unique across the table.
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    # Populated on onboarding step 1 (Company info) — nullable at signup because
    # signup only captures personal identity now (Tridge-style flow).
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # bcrypt hash. NULL for a brand-new account that only has a
    # temp credential — the user logs in with that, then is forced to
    # set a real password at /dashboard/settings/password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Set to True when the active login used the temp credential (so the
    # frontend knows to lock everything behind the change-password
    # screen) and cleared when the user sets a real password.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    # Set once the verify link is clicked.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.signed_up
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # ─── Verification audit ───────────────────────────────────
    # Captures when the user completed the 7 mandatory fields (auto-flip
    # into pending_verification), when an admin approved them, and the
    # admin's reason if the badge is denied. All three are nullable;
    # together they form the trail the UI needs to render the right
    # verification card state.
    verification_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_rejected_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Soft-delete for DPDP right-to-erasure.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    business_profile: Mapped["BusinessProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    verification_docs: Mapped[list["VerificationDoc"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
