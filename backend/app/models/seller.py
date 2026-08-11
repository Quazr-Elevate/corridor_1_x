from __future__ import annotations

import enum
import uuid

from sqlalchemy import CHAR, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class SellerOnboardingPath(str, enum.Enum):
    gstin = "gstin"
    pan = "pan"


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    onboarding_path: Mapped[SellerOnboardingPath] = mapped_column(
        Enum(SellerOnboardingPath, name="seller_onboarding_path"), nullable=False
    )
    # Unique partial index (WHERE gstin IS NOT NULL) added in the migration.
    gstin: Mapped[str | None] = mapped_column(CHAR(15), nullable=True)
    pan: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nature_of_business: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pincode: Mapped[str] = mapped_column(CHAR(6), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, server_default="India")

    user: Mapped[User] = relationship(back_populates="seller")
