from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, CheckConstraint, Date, Index, Numeric, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

#: Currencies a user may pick as ``display_currency`` (mirrors
#: FX_SUPPORTED_CURRENCIES; ck_users_display_currency enforces it).
SUPPORTED_CURRENCIES: tuple[str, ...] = ("INR", "AED", "USD")


class ExchangeRate(Base):
    """USD-based daily rate: ``1 USD = rate × quote`` on ``as_of``.

    Written only by the rate refresh (background task / cron script);
    requests read this table and never call a provider.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("base", "quote", "as_of", name="uq_exchange_rates_quote_day"),
        Index("ix_exchange_rates_latest", "quote", text("as_of DESC")),
        CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        CheckConstraint("length(base) = 3 AND length(quote) = 3", name="ck_exchange_rates_codes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    base: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="USD")
    quote: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    # frankfurter · fawazahmed0 · pegged · manual (· static in tests/offline)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
