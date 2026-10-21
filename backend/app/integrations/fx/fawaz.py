"""fawazahmed0 currency-api (https://github.com/fawazahmed0/exchange-api) —
free, no key, daily JSON files on the jsDelivr CDN with a Cloudflare Pages
mirror.

``GET .../v1/currencies/usd.min.json`` →

    {"date": "2026-10-17", "usd": {"aed": 3.6725, "inr": 94.97, ...}}

Keys are lowercase.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date

import httpx

from app.integrations.fx._http import get_json
from app.integrations.fx.base import FxConfig, FxError, FxProvider, FxRates, normalize_codes, to_rate

URLS = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json",
    "https://latest.currency-api.pages.dev/v1/currencies/usd.min.json",
)

log = logging.getLogger("app.integrations.fx.fawaz")


def parse_fawaz(payload: object, currencies: Iterable[str]) -> FxRates:
    if not isinstance(payload, dict) or not isinstance(payload.get("usd"), dict):
        raise FxError("fawazahmed0: expected {date, usd: {...}}")
    try:
        as_of = date.fromisoformat(str(payload.get("date")))
    except ValueError as e:
        raise FxError("fawazahmed0: missing/invalid date") from e
    table = payload["usd"]
    rates = {}
    for code in normalize_codes(currencies):
        rate = to_rate(table.get(code.lower()))
        if rate is not None:
            rates[code] = rate
    if not rates:
        raise FxError("fawazahmed0: no usable rates in the response")
    return FxRates(as_of=as_of, rates=rates, source=FawazProvider.name)


class FawazProvider(FxProvider):
    name = "fawazahmed0"

    def __init__(self, config: FxConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(config)
        self._transport = transport

    async def fetch_usd_rates(self, currencies: Iterable[str]) -> FxRates:
        codes = normalize_codes(currencies)
        if not codes:
            raise FxError("fawazahmed0: nothing to fetch")
        last: Exception | None = None
        for url in URLS:  # jsDelivr first, Cloudflare mirror second
            try:
                payload = await get_json(
                    url,
                    timeout=self.config.http_timeout_sec,
                    attempts=self.config.max_attempts,
                    label="fx:fawazahmed0",
                    transport=self._transport,
                )
                return parse_fawaz(payload, codes)
            except FxError as e:
                log.warning("fx: fawazahmed0 %s failed: %s", url, e)
                last = e
        raise FxError(f"fawazahmed0: every mirror failed ({last})")
