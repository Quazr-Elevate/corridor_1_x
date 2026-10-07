"""Single public entry — ``send_email()``.

Everything else in the host app routes through this one function so a
provider swap (console → Resend → SES) only touches env vars, never
business code.
"""
from __future__ import annotations

from pathlib import Path

from .config import EmailConfig
from .providers import (
    BrevoProvider,
    ConsoleProvider,
    EmailMessage,
    EmailProvider,
    ResendProvider,
)


_PROVIDERS: dict[str, type[EmailProvider]] = {
    "console": ConsoleProvider,
    "resend": ResendProvider,
    "brevo": BrevoProvider,
}


_default_config: EmailConfig | None = None
_provider_cache: dict[str, EmailProvider] = {}


def configure(config: EmailConfig) -> None:
    """Set the module-wide default config. Call once at app startup.

    Not required — ``send_email(..., config=...)`` works without it —
    but tidier than threading the config through every call site.
    """
    global _default_config
    _default_config = config
    _provider_cache.clear()


def _resolve(config: EmailConfig) -> EmailProvider:
    cls = _PROVIDERS.get(config.provider)
    if cls is None:
        raise ValueError(
            f"Unknown EMAIL_PROVIDER={config.provider!r}. "
            f"Expected one of: {', '.join(sorted(_PROVIDERS))}."
        )
    # Cache per-config so hosted providers reuse their underlying http
    # client. The cache key encodes provider + api_key + from, which
    # together describe one sending identity.
    key = f"{config.provider}|{config.api_key}|{config.from_address}|{config.outbox_dir}"
    if key not in _provider_cache:
        _provider_cache[key] = cls(config)
    return _provider_cache[key]


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    config: EmailConfig | None = None,
) -> Path | None:
    """Deliver one email via the active provider.

    Returns the console provider's .eml file path when that provider is
    active (handy to log alongside your signup record). Hosted
    providers return ``None`` — their delivery receipt is in the
    provider dashboard.
    """
    cfg = config or _default_config or EmailConfig.from_env()
    provider = _resolve(cfg)
    provider.send(EmailMessage(to=to, subject=subject, html=html, text=text))
    # Console path is useful to surface in dev tooling; everyone else
    # relies on their provider's dashboard.
    if isinstance(provider, ConsoleProvider):
        # The provider wrote the .eml in ``outbox_dir`` with a filename
        # we don't bubble back for simplicity — callers who need it can
        # list the folder themselves.
        return cfg.outbox_dir
    return None
