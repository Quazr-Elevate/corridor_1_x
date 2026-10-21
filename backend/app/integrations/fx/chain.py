"""Fallback chain: ask providers in order until every currency has a rate;
pegged currencies (AED) fall back to their peg."""
from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timezone

from app.integrations.fx.base import PEGGED_USD_RATES, FxError, FxProvider, FxQuote, normalize_codes

log = logging.getLogger("app.integrations.fx")


class FxChain:
    """Resolve each currency from the first provider that returns it."""

    def __init__(self, providers: Sequence[FxProvider]) -> None:
        self.providers = list(providers)

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.providers]

    async def fetch(self, currencies: Iterable[str], *, today: date | None = None) -> dict[str, FxQuote]:
        """``{quote: FxQuote}`` for every currency some provider (or a peg)
        could answer. Currencies nobody answered are simply absent — the
        caller keeps its last stored rate."""
        wanted = normalize_codes(currencies)
        found: dict[str, FxQuote] = {}
        for provider in self.providers:
            missing = [c for c in wanted if c not in found]
            if not missing:
                break
            try:
                answer = await provider.fetch_usd_rates(missing)
            except FxError as e:
                log.warning("fx: provider %s failed: %s", provider.name, e)
                continue
            except Exception:  # a provider bug must not break the chain
                log.exception("fx: provider %s crashed", provider.name)
                continue
            for code in missing:
                rate = answer.rates.get(code)
                if rate is not None:
                    found[code] = FxQuote(quote=code, rate=rate, as_of=answer.as_of, source=answer.source)
        day = today or datetime.now(tz=timezone.utc).date()
        for code in wanted:
            if code not in found and code in PEGGED_USD_RATES:
                log.warning("fx: no provider returned %s — using the peg %s", code, PEGGED_USD_RATES[code])
                found[code] = FxQuote(quote=code, rate=PEGGED_USD_RATES[code], as_of=day, source="pegged")
        return found
