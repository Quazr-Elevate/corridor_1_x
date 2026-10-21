"""Fixed rates — tests and offline development. Never touches the network."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from app.integrations.fx.base import FxError, FxProvider, FxRates, normalize_codes


class StaticProvider(FxProvider):
    name = "static"

    async def fetch_usd_rates(self, currencies: Iterable[str]) -> FxRates:
        table = {k.upper(): v for k, v in self.config.static_rates.items()}
        rates = {c: table[c] for c in normalize_codes(currencies) if c in table}
        if not rates:
            raise FxError("static: no configured rate for the requested currencies")
        return FxRates(as_of=datetime.now(tz=timezone.utc).date(), rates=rates, source=self.name)
