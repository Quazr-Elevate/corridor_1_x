"""Admin auth for the internal console.

Single-operator MVP: credentials live in env (`ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH`).
The session is a signed cookie carrying just the admin email + issued-at timestamp;
we verify the signature + freshness on every /admin/* call. When a second operator
joins, migrate to an `admin_users` table with a `role` enum and keep this signature
scheme.
"""
from __future__ import annotations

import time
from typing import Annotated

import bcrypt
from fastapi import Cookie, Depends, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

ADMIN_COOKIE_NAME = "cor1x_admin"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.admin_session_secret, salt="cor1x-admin-session"
    )


def verify_password(plaintext: str) -> bool:
    if not settings.admin_password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plaintext.encode("utf-8"),
            settings.admin_password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def issue_session(email: str) -> str:
    return _serializer().dumps({"email": email, "iat": int(time.time())})


def require_admin(
    cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE_NAME)] = None,
) -> str:
    if not cor1x_admin:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        payload = _serializer().loads(
            cor1x_admin,
            max_age=settings.admin_session_max_age_hours * 3600,
        )
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired") from None
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session") from None
    email = payload.get("email") if isinstance(payload, dict) else None
    if email != settings.admin_email:
        # Cookie was issued for a different admin identity — env changed since.
        raise HTTPException(status_code=401, detail="Session stale")
    return email


AdminEmail = Annotated[str, Depends(require_admin)]
