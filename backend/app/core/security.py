"""Passwords, signed tokens, cookies and admin auth.

Token kinds (all HMAC-signed with itsdangerous):

* ``cor1x_session`` cookie — ``{"uid": <uuid>, "sv": <session_version>}``,
  24h TTL. ``sv`` must equal ``users.session_version`` at request time, so
  bumping that column (password change, logout-everywhere, account delete)
  revokes every outstanding cookie. Cookies minted before ``sv`` existed are
  read as version 0.
* ``cor1x_admin`` cookie — ``{"email", "iat"}``, signed with the admin secret.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import bcrypt
from fastapi import Cookie, Depends, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings
from app.core.errors import Unauthorized

SESSION_COOKIE = "cor1x_session"
ADMIN_COOKIE = "cor1x_admin"

SESSION_MAX_AGE_SEC = 24 * 3600


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


# ── Helpers ──────────────────────────────────────────────────────────


def parse_uuid(raw: Any) -> uuid.UUID | None:
    """Token/cookie payloads carry ids as strings; the Uuid column needs a
    UUID object (SQLite's non-native Uuid binding rejects plain str)."""
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def cookie_policy() -> tuple[str, bool]:
    """(samesite, secure) — driven by CROSS_SITE_COOKIES, not DEBUG.

    Cross-site HTTPS deployments need ``SameSite=None; Secure``; local
    http://localhost dev uses ``lax`` + insecure (Secure cookies are dropped
    over plain http).
    """
    if settings.cross_site_cookies:
        return "none", True
    return "lax", False


def _serializer(secret: str, salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=salt)


# ── User session ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionClaims:
    user_id: uuid.UUID
    session_version: int


def issue_session_token(user_id: uuid.UUID | str, session_version: int) -> str:
    return _serializer(settings.session_secret, "cor1x-user-session").dumps(
        {"uid": str(user_id), "sv": int(session_version)}
    )


def decode_session_token(token: str | None) -> SessionClaims | None:
    if not token:
        return None
    try:
        payload: Any = _serializer(settings.session_secret, "cor1x-user-session").loads(
            token, max_age=SESSION_MAX_AGE_SEC
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    uid = parse_uuid(payload.get("uid"))
    sv = payload.get("sv", 0)
    if uid is None or not isinstance(sv, int):
        return None
    return SessionClaims(user_id=uid, session_version=sv)


def set_session_cookie(response: Response, user_id: uuid.UUID | str, session_version: int) -> None:
    samesite, secure = cookie_policy()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=issue_session_token(user_id, session_version),
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    samesite, secure = cookie_policy()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite=samesite, secure=secure, httponly=True)


def frontend_url(path: str) -> str:
    return f"{settings.frontend_base}/{path.lstrip('/')}"


# ── Admin auth ───────────────────────────────────────────────────────


def verify_admin_credentials(email: str, password: str) -> bool:
    if email.strip().lower() != settings.admin_email.strip().lower():
        # Still burn a bcrypt round so timing doesn't reveal the email.
        verify_password(password, settings.admin_password_hash or None)
        return False
    return verify_password(password, settings.admin_password_hash or None)


def issue_admin_token(email: str) -> str:
    return _serializer(settings.admin_session_secret, "cor1x-admin-session").dumps(
        {"email": email, "iat": int(time.time())}
    )


def decode_admin_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload: Any = _serializer(settings.admin_session_secret, "cor1x-admin-session").loads(
            token, max_age=settings.admin_session_max_age_hours * 3600
        )
    except (BadSignature, SignatureExpired):
        return None
    email = payload.get("email") if isinstance(payload, dict) else None
    # Cookie issued for a different admin identity (env changed) → stale.
    return email if email == settings.admin_email else None


def set_admin_cookie(response: Response, email: str) -> None:
    samesite, secure = cookie_policy()
    response.set_cookie(
        key=ADMIN_COOKIE,
        value=issue_admin_token(email),
        max_age=settings.admin_session_max_age_hours * 3600,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )


def clear_admin_cookie(response: Response) -> None:
    samesite, secure = cookie_policy()
    response.delete_cookie(ADMIN_COOKIE, path="/", samesite=samesite, secure=secure, httponly=True)


def require_admin(
    cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
) -> str:
    email = decode_admin_token(cor1x_admin)
    if email is None:
        raise Unauthorized("Not signed in")
    return email


def optional_admin(
    cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
) -> str | None:
    return decode_admin_token(cor1x_admin)


AdminEmail = Annotated[str, Depends(require_admin)]
