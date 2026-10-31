"""Passwords, session tokens, cookies and IP truncation.

Sessions are server-side (``user_sessions`` / ``admin_sessions``, see
``app/modules/auth/sessions.py``). The cookie holds a random opaque token;
the database stores only its SHA-256, so revoking a row ends the session
immediately and a database leak can't be replayed as live cookies.

* ``cor1x_session`` — trader session cookie.
* ``cor1x_admin``   — admin console session cookie.
"""
from __future__ import annotations

import hashlib
import ipaddress
import secrets
import uuid
from typing import Any

import bcrypt
from fastapi import Response

from app.core.config import settings

SESSION_COOKIE = "cor1x_session"
ADMIN_COOKIE = "cor1x_admin"


# ── Passwords ────────────────────────────────────────────────────────


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def temporary_password() -> str:
    """Readable one-time password for admin-created accounts (~95 bits)."""
    return "-".join(secrets.token_urlsafe(6) for _ in range(3))


# ── Helpers ──────────────────────────────────────────────────────────


def parse_uuid(raw: Any) -> uuid.UUID | None:
    """Path params / payloads carry ids as strings; the Uuid column needs a
    UUID object (SQLite's non-native Uuid binding rejects plain str)."""
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def frontend_url(path: str) -> str:
    return f"{settings.frontend_base}/{path.lstrip('/')}"


def ip_prefix(ip: str | None) -> str | None:
    """Truncate an address before storing it: IPv4 → /24, IPv6 → /48.

    Enough to recognise a network in an investigation, not enough to
    identify a household."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))


def ip_allowed(ip: str | None, allowlist: list[str]) -> bool:
    """Empty allowlist = no restriction."""
    if not allowlist:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


# ── Session tokens + cookies ─────────────────────────────────────────


def new_session_token() -> tuple[str, str]:
    """``(token, sha256 hex)`` — the token goes in the cookie, the hash in the DB."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cookie_policy() -> tuple[str, bool]:
    """(samesite, secure).

    Cross-site HTTPS deployments need ``SameSite=None; Secure``. Otherwise
    ``lax``, and ``Secure`` unless DEBUG is on (plain http://localhost drops
    Secure cookies) — see ``Settings.secure_cookies``.
    """
    return ("none" if settings.cross_site_cookies else "lax"), settings.secure_cookies


def set_cookie(response: Response, name: str, token: str, max_age_sec: int) -> None:
    samesite, secure = cookie_policy()
    response.set_cookie(
        key=name, value=token, max_age=max_age_sec, httponly=True, samesite=samesite, secure=secure, path="/"
    )


def clear_cookie(response: Response, name: str) -> None:
    samesite, secure = cookie_policy()
    response.delete_cookie(name, path="/", samesite=samesite, secure=secure, httponly=True)
