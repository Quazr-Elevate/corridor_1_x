"""Frankfurter v2 (https://frankfurter.dev) — free, no key, open source,
self-hostable; data from central banks (ECB and others).

``GET https://api.frankfurter.dev/v2/rates?base=USD&quotes=INR,AED`` →

    [{"date": "2026-10-17", "base": "USD", "quote": "AED", "rate": 3.6725},
     {"date": "2026-10-17", "base": "USD", "quote": "INR", "rate": 94.94}]

On weekends / holidays ``date`` is the last working day.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import httpx

from app.integrations.fx._http import get_json
from app.integrations.fx.base import FxConfig, FxError, FxProvider, FxRates, normalize_codes, to_rate

URL = "https://api.frankfurter.dev/v2/rates"


def parse_frankfurter(payload: object, currencies: Iterable[str]) -> FxRates:
    wanted = set(normalize_codes(currencies))
    if not isinstance(payload, list):
        raise FxError("frankfurter: expected a JSON list")
    rates = {}
    dates: list[date] = []
    for item in payload:
        if not isinstance(item, dict) or str(item.get("base", "")).upper() != "USD":
            continue
        quote = str(item.get("quote", "")).upper()
        rate = to_rate(item.get("rate"))
        if quote not in wanted or rate is None:
            continue
        try:
            dates.append(date.fromisoformat(str(item.get("date"))))
        except ValueError:
            continue
        rates[quote] = rate
    if not rates:
        raise FxError("frankfurter: no usable rates in the response")
    return FxRates(as_of=max(dates), rates=rates, source=FrankfurterProvider.name)


class FrankfurterProvider(FxProvider):
    name = "frankfurter"

    def __init__(self, config: FxConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(config)
        self._transport = transport

    async def fetch_usd_rates(self, currencies: Iterable[str]) -> FxRates:
        codes = normalize_codes(currencies)
        if not codes:
            raise FxError("frankfurter: nothing to fetch")
        payload = await get_json(
            URL,
            params={"base": "USD", "quotes": ",".join(codes)},
            timeout=self.config.http_timeout_sec,
            attempts=self.config.max_attempts,
            label="fx:frankfurter",
            transport=self._transport,
        )
        return parse_frankfurter(payload, codes)
