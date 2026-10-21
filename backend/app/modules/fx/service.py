"""Exchange-rate rules: store daily USD rates, read the latest ones,
convert amounts, keep ``products.price_usd`` in sync.

Requests only ever read the ``exchange_rates`` table — providers are called
by :func:`refresh_rates` (background task / cron script), never while a
user waits.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from sqlalchemy import Numeric, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import BadRequest, ServiceUnavailable
from app.core.time import utcnow
from app.integrations.fx import FxChain, FxQuote, get_fx_chain
from app.models.exchange_rate import ExchangeRate
from app.models.product import Product

log = logging.getLogger("app.fx")

BASE = "USD"
CENT = Decimal("0.01")
#: Sources that are placeholders, not a real fetch (the 0020 bootstrap).
BOOTSTRAP_SOURCES = frozenset({"manual"})


def supported_currencies() -> tuple[str, ...]:
    return settings.fx_currency_list


def ensure_supported(code: str | None, *, what: str = "Currency") -> str:
    c = (code or "").strip().upper()
    if c not in supported_currencies():
        raise BadRequest(f"{what} must be one of {', '.join(supported_currencies())}.")
    return c


# ── Reading ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LatestRates:
    """Latest stored rate per supported currency (``USD`` is always 1)."""

    rates: dict[str, Decimal]
    as_of_by: dict[str, date] = field(default_factory=dict)
    source_by: dict[str, str] = field(default_factory=dict)

    @property
    def as_of(self) -> date | None:
        """The oldest of the per-currency dates — what "rate of <date>" means
        for a mix of currencies."""
        return min(self.as_of_by.values()) if self.as_of_by else None

    @property
    def source(self) -> str | None:
        sources = sorted(set(self.source_by.values()))
        return ",".join(sources) if sources else None

    def rate(self, code: str | None) -> Decimal | None:
        return self.rates.get((code or "").upper())


async def _latest_row(db: AsyncSession, quote: str) -> ExchangeRate | None:
    return await db.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.base == BASE, ExchangeRate.quote == quote)
        .order_by(ExchangeRate.as_of.desc(), ExchangeRate.fetched_at.desc())
        .limit(1)
    )


async def get_latest_rates(db: AsyncSession) -> LatestRates:
    rates: dict[str, Decimal] = {BASE: Decimal(1)}
    as_of_by: dict[str, date] = {}
    source_by: dict[str, str] = {}
    for code in supported_currencies():
        if code == BASE:
            continue
        row = await _latest_row(db, code)
        if row is not None:
            rates[code] = Decimal(row.rate)
            as_of_by[code] = row.as_of
            source_by[code] = row.source
    return LatestRates(rates=rates, as_of_by=as_of_by, source_by=source_by)


def convert(amount: Decimal, from_currency: str, to_currency: str, rates: LatestRates) -> Decimal | None:
    """``amount`` in ``from_currency`` → ``to_currency`` (unrounded), or
    None when either rate is unknown."""
    src, dst = rates.rate(from_currency), rates.rate(to_currency)
    if src is None or dst is None:
        return None
    return Decimal(amount) / src * dst


def price_usd_for(price: Decimal | None, currency: str, rates: LatestRates) -> tuple[Decimal | None, date | None]:
    """``(price_usd, price_usd_as_of)`` for a listing price."""
    if price is None:
        return None, None
    usd = convert(price, currency, BASE, rates)
    if usd is None:
        return None, None
    as_of = rates.as_of_by.get(currency.upper()) or utcnow().date()
    return usd.quantize(CENT, rounding=ROUND_HALF_UP), as_of


async def usd_bounds(
    db: AsyncSession, min_price: Decimal | None, max_price: Decimal | None, currency: str | None
) -> tuple[Decimal | None, Decimal | None]:
    """Market filter bounds typed in ``currency`` (default USD) → USD, widened
    to whole cents (min floored, max ceiled) so a bound equal to a listing's
    own price still matches its rounded ``price_usd``."""
    code = ensure_supported(currency or BASE, what="priceCurrency")
    if min_price is None and max_price is None:
        return None, None
    rates = await get_latest_rates(db)
    if rates.rate(code) is None:
        raise ServiceUnavailable("Exchange rates aren't available yet — try again shortly.")

    def _usd(v: Decimal | None, rounding: str) -> Decimal | None:
        if v is None:
            return None
        return convert(v, code, BASE, rates).quantize(CENT, rounding=rounding)  # type: ignore[union-attr]

    return _usd(min_price, ROUND_FLOOR), _usd(max_price, ROUND_CEILING)


# ── Refreshing ───────────────────────────────────────────────────────


@dataclass
class RefreshResult:
    stored: list[FxQuote] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    products_updated: int = 0


def _sane(quote: FxQuote, last: ExchangeRate | None, max_change: Decimal) -> str | None:
    """Why ``quote`` must be rejected, or None when it looks plausible."""
    if quote.rate is None or not quote.rate.is_finite() or quote.rate <= 0:
        return f"non-positive rate {quote.rate}"
    if last is None:
        return None
    prev = Decimal(last.rate)
    change = abs(quote.rate - prev) / prev
    if change > max_change:
        return f"moved {change:.1%} vs last stored {prev} ({last.as_of}, {last.source})"
    return None


async def _upsert(db: AsyncSession, quote: FxQuote) -> None:
    row = await db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.base == BASE, ExchangeRate.quote == quote.quote, ExchangeRate.as_of == quote.as_of
        )
    )
    if row is None:
        db.add(ExchangeRate(base=BASE, quote=quote.quote, rate=quote.rate, as_of=quote.as_of, source=quote.source,
                            fetched_at=utcnow()))
    else:
        row.rate = quote.rate
        row.source = quote.source
        row.fetched_at = utcnow()


async def recompute_price_usd(db: AsyncSession, rates: LatestRates | None = None) -> int:
    """Refresh ``price_usd`` / ``price_usd_as_of`` of every non-deleted
    listing — one UPDATE per currency. Returns the rows touched."""
    rates = rates or await get_latest_rates(db)
    touched = 0
    today = utcnow().date()
    for code, rate in rates.rates.items():
        priced = (
            Product.currency == code,
            Product.deleted_at.is_(None),
            Product.price_per_unit.is_not(None),
        )
        value = (
            Product.price_per_unit
            if code == BASE
            else func.round(Product.price_per_unit / literal(rate, Numeric(18, 8)), 2)
        )
        result = await db.execute(
            update(Product)
            .where(*priced)
            .values(price_usd=value, price_usd_as_of=rates.as_of_by.get(code, today))
            .execution_options(synchronize_session=False)
        )
        touched += result.rowcount or 0
    await db.commit()
    return touched


async def refresh_rates(db: AsyncSession, chain: FxChain | None = None) -> RefreshResult:
    """Fetch today's USD rates (fallback chain + AED peg), store the sane
    ones (one row per currency per day), then recompute every listing's
    ``price_usd``. A rejected or missing currency keeps its last rate."""
    chain = chain or get_fx_chain()
    wanted = [c for c in supported_currencies() if c != BASE]
    quotes = await chain.fetch(wanted)
    max_change = Decimal(str(settings.fx_max_change_pct)) / 100
    result = RefreshResult(missing=[c for c in wanted if c not in quotes])
    for code in result.missing:
        log.warning("fx: no rate for %s from %s — keeping the last stored one", code, ",".join(chain.names))
    for code, quote in quotes.items():
        reason = _sane(quote, await _latest_row(db, code), max_change)
        if reason:
            log.warning("fx: rejected %s=%s from %s: %s — keeping the last stored rate", code, quote.rate,
                        quote.source, reason)
            result.rejected.append(code)
            continue
        await _upsert(db, quote)
        result.stored.append(quote)
    await db.commit()
    result.products_updated = await recompute_price_usd(db)
    log.info(
        "fx: refresh stored=%s rejected=%s missing=%s products=%d",
        {q.quote: f"{q.rate} ({q.source}, {q.as_of})" for q in result.stored},
        result.rejected,
        result.missing,
        result.products_updated,
    )
    return result


async def refresh_due(db: AsyncSession) -> bool:
    """True when some supported currency has no rate fetched today (UTC) or
    only the bootstrap placeholder."""
    today = utcnow().date()
    for code in supported_currencies():
        if code == BASE:
            continue
        row = await db.scalar(
            select(ExchangeRate)
            .where(ExchangeRate.base == BASE, ExchangeRate.quote == code)
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        if row is None or row.source in BOOTSTRAP_SOURCES:
            return True
        fetched = row.fetched_at
        if fetched is None or fetched.date() < today:
            return True
    return False
