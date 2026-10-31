"""Transactional notifications.

Owns message content (Jinja2 templates in ``templates/``: ``<name>.html`` +
``<name>.txt``) and delivery through the email integration. Routers and
services call the typed functions below and never build email bodies.

* ``send_*`` functions raise on delivery failure (use when the caller must
  know, e.g. the signup code mail).
* :func:`deliver_safely` wraps any of them for ``BackgroundTasks`` — it
  logs failures instead of raising.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.config import settings
from app.core.security import frontend_url
from app.integrations.email import send_email

log = logging.getLogger("app.notifications")

_TEMPLATES = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


def render(name: str, **context: Any) -> tuple[str, str]:
    """Return ``(html, text)`` for template ``name``."""
    return _env.get_template(f"{name}.html").render(**context), _env.get_template(f"{name}.txt").render(**context)


async def _send(to: str, subject: str, template: str, **context: Any) -> None:
    html, text = render(template, **context)
    await send_email(to=to, subject=subject, html=html, text=text)


def first_name_of(full_name: str | None) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else "there"


# ── Typed messages ───────────────────────────────────────────────────


async def send_signup_code(*, to: str, code: str, valid_minutes: int) -> None:
    await _send(
        to,
        f"{code} is your Cor1x verification code",
        "signup_code",
        code=code,
        email=to,
        valid_minutes=valid_minutes,
    )


async def send_password_reset_code(*, to: str, code: str, first_name: str, valid_minutes: int) -> None:
    await _send(
        to,
        f"{code} is your Cor1x password reset code",
        "password_reset_code",
        code=code,
        first_name=first_name,
        valid_minutes=valid_minutes,
        support_email=settings.support_email,
    )


async def send_verification_approved(*, to: str, first_name: str) -> None:
    await _send(
        to,
        "You're verified on Cor1x",
        "verification_approved",
        first_name=first_name,
        dashboard_url=frontend_url("/dashboard"),
    )


async def send_verification_rejected(*, to: str, first_name: str, reason: str) -> None:
    await _send(
        to,
        "Your Cor1x verification needs changes",
        "verification_rejected",
        first_name=first_name,
        reason=reason,
        account_url=frontend_url("/dashboard/account"),
    )


async def send_doc_rejected(*, to: str, first_name: str, cert_type: str, reason: str) -> None:
    await _send(
        to,
        f"Action needed: your {cert_type} was not accepted",
        "doc_rejected",
        first_name=first_name,
        cert_type=cert_type,
        reason=reason,
        account_url=frontend_url("/dashboard/account"),
    )


async def deliver_safely(fn: Callable[..., Awaitable[None]], /, **kwargs: Any) -> None:
    """Run a ``send_*`` function, logging (not raising) failures. Intended
    for ``background_tasks.add_task(deliver_safely, send_x, **kwargs)``."""
    try:
        await fn(**kwargs)
    except Exception:  # noqa: BLE001
        log.exception("notification_failed fn=%s to=%s", getattr(fn, "__name__", fn), kwargs.get("to"))


__all__ = [
    "deliver_safely",
    "first_name_of",
    "render",
    "send_doc_rejected",
    "send_verification_approved",
    "send_verification_rejected",
    "send_signup_code",
]
