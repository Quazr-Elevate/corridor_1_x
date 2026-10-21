from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, JSON, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class Product(Base):
    """A business's listing. Agri-generic (rice, sugar, wheat, pulses,
    spices, oilseeds, cotton, millets, tea, coffee, other).

    Visible in the market only when the product is not deleted AND the
    owning business is ``verified`` and not deleted.
    """

    __tablename__ = "products"
    __table_args__ = (
        Index(
            "ix_products_market",
            "category",
            text("created_at DESC"),
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_products_market_all",
            text("created_at DESC"),
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_products_business",
            "business_id",
            text("created_at DESC"),
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_products_created_by", "created_by_user_id"),
        Index(
            "ix_products_market_price",
            "category",
            "price_usd",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "category IN ('Rice', 'Sugar', 'Wheat', 'Pulses', 'Spices', 'Oilseeds', "
            "'Cotton', 'Millets', 'Tea', 'Coffee', 'Other')",
            name="ck_products_category",
        ),
        CheckConstraint("unit IN ('MT', 'kg', 'quintal')", name="ck_products_unit"),
        CheckConstraint("length(currency) = 3", name="ck_products_currency"),
        CheckConstraint(
            "(quantity IS NULL OR quantity >= 0) AND (moq IS NULL OR moq >= 0) "
            "AND (price_per_unit IS NULL OR price_per_unit >= 0)",
            name="ck_products_amounts",
        ),
        CheckConstraint(
            "moq IS NULL OR quantity IS NULL OR moq <= quantity", name="ck_products_moq_le_quantity"
        ),
        CheckConstraint("length(trim(name)) >= 2", name="ck_products_name_length"),
        CheckConstraint("price_usd IS NULL OR price_usd >= 0", name="ck_products_price_usd"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_products_business_id"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_products_created_by_user_id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    packaging: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="MT", server_default="MT")
    moq: Mapped[Decimal | None] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="INR", server_default="INR")
    # price_per_unit ÷ rate(currency) — for cross-currency filtering only;
    # the seller's price is never changed. NULL when unpriced / no rate.
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2), nullable=True)
    # Which day's rate produced price_usd.
    price_usd_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Relative photo URLs produced by POST /products/upload-photo (1–5).
    photos: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
