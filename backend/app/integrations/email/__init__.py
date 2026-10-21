"""Reusable async email module (console / Resend / Brevo).

    from app.integrations.email import configure, EmailConfig, send_email
    configure(EmailConfig(provider="resend", api_key="re_...", from_address="hi@x.com"))
    await send_email(to="a@b.com", subject="Hi", html="<p>Hi</p>", text="Hi")

The console provider prints mail, writes .eml files to ``outbox_dir`` and
keeps recent messages in ``provider.sent``. Hosted providers retry
transient failures (network, 429, 5xx) with exponential backoff.
"""
from app.integrations.email.base import (
    EmailConfig,
    EmailDeliveryError,
    EmailMessage,
    EmailProvider,
)
from app.integrations.email.factory import (
    PROVIDERS,
    build_provider,
    configure,
    get_provider,
    send_email,
    set_provider,
)
from app.integrations.email.validators import EmailRejection, assert_work_email

__all__ = [
    "PROVIDERS",
    "EmailConfig",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailProvider",
    "EmailRejection",
    "assert_work_email",
    "build_provider",
    "configure",
    "get_provider",
    "send_email",
    "set_provider",
]
