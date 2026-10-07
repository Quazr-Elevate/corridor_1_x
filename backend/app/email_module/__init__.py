"""Reusable email module — self-contained, drop-copyable to any Python
project. The only runtime dependency is ``httpx`` (for the Resend /
Brevo adapters). The console adapter uses just the stdlib.

Public surface::

    from app.email_module import send_email
    from app.email_module import assert_work_email, EmailRejection
    from app.email_module import EmailConfig, EmailMessage

    send_email(to="x@y.com", subject="hi", html="<p>…</p>", text="…")

The provider is picked up from ``EMAIL_PROVIDER`` (console / resend /
brevo). Any copy of this module can run with no config at all — the
console provider prints to stdout AND writes an .eml file so the local
dev loop never needs an inbox.
"""
from __future__ import annotations

from .config import EmailConfig
from .providers.base import EmailMessage, EmailProvider
from .send import send_email
from .validators import EmailRejection, assert_work_email

__all__ = [
    "EmailConfig",
    "EmailMessage",
    "EmailProvider",
    "EmailRejection",
    "assert_work_email",
    "send_email",
]
