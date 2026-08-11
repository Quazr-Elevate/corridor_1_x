from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Otp(Base):
    __tablename__ = "otps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    identity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("identities.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
