from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.business_profile import BusinessProfile
    from app.models.identity import Identity
    from app.models.profile import Profile


class UserStatus(str, enum.Enum):
    """Verification funnel — same enum for buyers and sellers, semantics differ.

    Buyer path: signed_up → verified (admin OK) → rejected.
    Seller path: signed_up → profile_complete (business + bank filled)
                 → verified (admin OK) → rejected.
    """

    signed_up = "signed_up"
    profile_complete = "profile_complete"
    verified = "verified"
    rejected = "rejected"


class User(Base):
    """Thin auth account. Role (buyer/seller) is DERIVED, not stored:
    a user is a seller iff they have at least one row in `products`.
    """

    __tablename__ = "users"

    # sa.Uuid is portable: native UUID on Postgres, CHAR(32) hex on SQLite.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.signed_up
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Soft-delete for DPDP right-to-erasure. Hard-delete via cleanup job later.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    identities: Mapped[list["Identity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    business_profile: Mapped["BusinessProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
