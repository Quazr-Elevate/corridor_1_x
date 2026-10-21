"""Exchange-rate provider interface — app-agnostic.

Every provider answers one question: "how many units of each quote currency
is 1 USD worth today?" (``1 USD = rate × quote``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

#: Currencies with an official USD peg — used when no provider returns them.
PEGGED_USD_RATES: dict[str, Decimal] = {"AED": Decimal("3.6725")}

#: Offline / test defaults for the static provider (1 USD = rate × quote).
DEFAULT_STATIC_RATES: dict[str, Decimal] = {"INR": Decimal("95"), "AED": Decimal("3.6725")}


@dataclass(frozen=True)
class FxConfig:
    """Everything the module needs (no app settings imported)."""

    #: Provider names, tried in order (see ``PROVIDERS``).
    providers: tuple[str, ...] = ("frankfurter", "fawazahmed0")
    http_timeout_sec: float = 10.0
    #: Total tries per URL on transient failures (network, 429, 5xx).
    max_attempts: int = 3
    #: Rates served by the ``static`` provider.
    static_rates: dict[str, Decimal] = field(default_factory=lambda: dict(DEFAULT_STATIC_RATES))


@dataclass(frozen=True)
class FxRates:
    """One provider's answer: ``rates[quote]`` = units of quote per 1 USD."""

    as_of: date
    rates: dict[str, Decimal]
    source: str


@dataclass(frozen=True)
class FxQuote:
    """One currency's rate after the fallback chain resolved it."""

    quote: str
    rate: Decimal
    as_of: date
    source: str


class FxError(Exception):
    """The provider could not deliver rates (network, bad payload, …)."""


def to_rate(value: object) -> Decimal | None:
    """Positive finite Decimal from a JSON number/string, else None."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() and d > 0 else None


def normalize_codes(currencies: Iterable[str]) -> list[str]:
    """Upper-cased, de-duplicated, without USD (USD→USD is always 1)."""
    out: list[str] = []
    for c in currencies:
        code = c.strip().upper()
        if code and code != "USD" and code not in out:
            out.append(code)
    return out


class FxProvider(ABC):
    name: str = "base"

    def __init__(self, config: FxConfig) -> None:
        self.config = config

    @abstractmethod
    async def fetch_usd_rates(self, currencies: Iterable[str]) -> FxRates:
        """USD-based rates for ``currencies`` (any subset may be missing
        from the answer). Raises :class:`FxError` when nothing usable came
        back."""
