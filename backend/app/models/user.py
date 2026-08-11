from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.buyer import Buyer
    from app.models.identity import Identity
    from app.models.seller import Seller


class UserType(str, enum.Enum):
    seller = "seller"
    buyer = "buyer"


class UserStatus(str, enum.Enum):
    signed_up = "signed_up"
    profile_complete = "profile_complete"
    verified = "verified"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    # sa.Uuid is portable: native UUID on Postgres, CHAR(32) hex on SQLite.
    # UUID is generated Python-side so we don't depend on gen_random_uuid().
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_type: Mapped[UserType] = mapped_column(Enum(UserType, name="user_type"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.signed_up
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    identities: Mapped[list["Identity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    seller: Mapped["Seller | None"] = relationship(back_populates="user", uselist=False)
    buyer: Mapped["Buyer | None"] = relationship(back_populates="user", uselist=False)
