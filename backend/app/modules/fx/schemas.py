from __future__ import annotations

from datetime import date

from app.shared.schemas import CamelModel


class FxRatesOut(CamelModel):
    """``1 USD = rates[code] × code``. Indicative, for display/filters only."""

    base: str = "USD"
    as_of: date | None = None
    rates: dict[str, float]
    source: str | None = None
