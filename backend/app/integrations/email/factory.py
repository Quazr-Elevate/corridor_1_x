"""Provider registry + the single ``send_email`` entry point."""
from __future__ import annotations

from app.integrations.email.base import EmailConfig, EmailMessage, EmailProvider
from app.integrations.email.providers import BrevoProvider, ConsoleProvider, ResendProvider

PROVIDERS: dict[str, type[EmailProvider]] = {
    "console": ConsoleProvider,
    "resend": ResendProvider,
    "brevo": BrevoProvider,
}

_config: EmailConfig | None = None
_provider: EmailProvider | None = None


def build_provider(config: EmailConfig) -> EmailProvider:
    cls = PROVIDERS.get(config.provider.strip().lower())
    if cls is None:
        raise ValueError(
            f"Unknown EMAIL_PROVIDER={config.provider!r}. Expected one of: {', '.join(sorted(PROVIDERS))}."
        )
    return cls(config)


def configure(config: EmailConfig) -> None:
    """Set the process-wide config (call once at startup). The provider is
    built lazily so a misconfigured hosted provider fails on first send,
    not at import."""
    global _config, _provider
    _config = config
    _provider = None


def get_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        _provider = build_provider(_config or EmailConfig())
    return _provider


def set_provider(provider: EmailProvider | None) -> None:
    """Override the active provider (tests)."""
    global _provider
    _provider = provider


async def send_email(*, to: str, subject: str, html: str, text: str) -> None:
    """Deliver one message via the active provider (async, non-blocking).
    Raises :class:`EmailDeliveryError` (or ``RuntimeError`` for
    misconfiguration) on failure."""
    await get_provider().send(EmailMessage(to=to, subject=subject, html=html, text=text))
