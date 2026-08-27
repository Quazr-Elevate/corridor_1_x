from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Buyer(Base):
    """Primary profile row for every signed-up user (buyer is the default type;
    a user upgrades to seller when they add their first product). Holds
    contact, address, and additional/social details shared across roles."""

    __tablename__ = "buyers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Primary details
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    # Historical fields (kept nullable now; company_name is captured under Business)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Additional details
    alt_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alt_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    google_business_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    user: Mapped[User] = relationship(back_populates="buyer")
