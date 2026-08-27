from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BankDetails(Base):
    """One bank account per user (payout account). Account number stored
    plain for dev; production must vault this or store only a token from
    the payments provider (Razorpay Route / Cashfree Payouts)."""

    __tablename__ = "bank_details"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    account_number: Mapped[str] = mapped_column(String(30), nullable=False)
    ifsc: Mapped[str] = mapped_column(String(11), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
