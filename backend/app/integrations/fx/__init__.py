"""Reusable USD-based exchange-rate module (frankfurter / fawazahmed0 / static).

    from app.integrations.fx import configure_fx, FxConfig, get_fx_chain
    configure_fx(FxConfig(providers=("frankfurter", "fawazahmed0")))
    quotes = await get_fx_chain().fetch(["INR", "AED"])   # {code: FxQuote}

Providers are tried in order per currency; ``AED`` falls back to its USD
peg (3.6725). HTTP providers retry transient failures with backoff.
"""
from __future__ import annotations

from app.integrations.fx.base import (
    DEFAULT_STATIC_RATES,
    PEGGED_USD_RATES,
    FxConfig,
    FxError,
    FxProvider,
    FxQuote,
    FxRates,
)
from app.integrations.fx.chain import FxChain
from app.integrations.fx.fawaz import FawazProvider, parse_fawaz
from app.integrations.fx.frankfurter import FrankfurterProvider, parse_frankfurter
from app.integrations.fx.static import StaticProvider

PROVIDERS: dict[str, type[FxProvider]] = {
    "frankfurter": FrankfurterProvider,
    "fawazahmed0": FawazProvider,
    "static": StaticProvider,
}

_config: FxConfig | None = None
_chain: FxChain | None = None


def build_fx_chain(config: FxConfig) -> FxChain:
    providers = []
    for raw in config.providers:
        name = raw.strip().lower()
        if not name:
            continue
        cls = PROVIDERS.get(name)
        if cls is None:
            raise ValueError(f"Unknown FX provider {raw!r}. Expected one of: {', '.join(sorted(PROVIDERS))}.")
        providers.append(cls(config))
    if not providers:
        raise ValueError("FX_PROVIDERS is empty.")
    return FxChain(providers)


def configure_fx(config: FxConfig) -> None:
    global _config, _chain
    _config = config
    _chain = None


def get_fx_chain() -> FxChain:
    global _chain
    if _chain is None:
        _chain = build_fx_chain(_config or FxConfig())
    return _chain


def set_fx_chain(chain: FxChain | None) -> None:
    """Override the active chain (tests)."""
    global _chain
    _chain = chain


__all__ = [
    "DEFAULT_STATIC_RATES",
    "PEGGED_USD_RATES",
    "PROVIDERS",
    "FawazProvider",
    "FrankfurterProvider",
    "FxChain",
    "FxConfig",
    "FxError",
    "FxProvider",
    "FxQuote",
    "FxRates",
    "StaticProvider",
    "build_fx_chain",
    "configure_fx",
    "get_fx_chain",
    "parse_fawaz",
    "parse_frankfurter",
    "set_fx_chain",
]
