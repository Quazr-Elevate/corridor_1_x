from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContactReveal(Base):
    """Audit log: buyer X unlocked seller Y's contact for product Z.

    Idempotent per (buyer, product) — reveal is a one-time consent grant.
    Second click on the same product returns the same row (via UNIQUE), so
    a legitimate buyer who bookmarked a product doesn't have to re-trigger
    the gate. Rate-limiting to catch scrapers lives at the router layer.

    Kept lean — no arbitrary metadata columns. Analytics ("which products
    drive the most reveals") come from JOINs, not denormalized fields.
    """

    __tablename__ = "contact_reveals"
    __table_args__ = (
        UniqueConstraint("buyer_id", "product_id", name="uq_reveals_buyer_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized for cheap JOINs on the admin feed. Cascade so a
    # rejected/deleted seller's reveals disappear with them.
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
