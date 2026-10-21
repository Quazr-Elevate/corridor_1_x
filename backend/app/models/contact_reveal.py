from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class ContactReveal(Base):
    """Ledger of introductions: buyer business X unlocked seller business
    Y's contact for product Z.

    Idempotent per (buyer business, product) — a second click returns the
    same row. ``(buyer_business_id, revealed_at)`` backs the 20-per-hour
    limit per buyer business.
    """

    __tablename__ = "contact_reveals"
    __table_args__ = (
        UniqueConstraint("buyer_business_id", "product_id", name="uq_contact_reveals_buyer_product"),
        Index("ix_contact_reveals_buyer_time", "buyer_business_id", text("revealed_at DESC")),
        Index("ix_contact_reveals_seller_time", "seller_business_id", text("revealed_at DESC")),
        Index("ix_contact_reveals_product", "product_id"),
        Index("ix_contact_reveals_revealed_by", "revealed_by_user_id"),
        CheckConstraint("buyer_business_id <> seller_business_id", name="ck_contact_reveals_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_contact_reveals_buyer_business_id"), nullable=False
    )
    revealed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_contact_reveals_revealed_by_user_id"), nullable=True
    )
    seller_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_contact_reveals_seller_business_id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE", name="fk_contact_reveals_product_id"), nullable=False
    )
    revealed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
