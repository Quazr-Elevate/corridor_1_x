"""Signed cookies for the app.

Two token kinds, both HMAC-signed by :data:`settings.session_secret`:

1. ``cor1x_session`` — set on login and after set-password. Carries the
   user's UUID. Verified on every authenticated request via
   :func:`get_current_user` (deps.py). 24-hour TTL.

2. Signup verification tokens — the value embedded in the click-to-verify
   URL emailed to the user. Carries the user's UUID. 24-hour TTL.
"""
from __future__ import annotations

from typing import Any

from fastapi import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

SESSION_COOKIE = "cor1x_session"

SESSION_MAX_AGE_SEC = 24 * 3600
VERIFY_TOKEN_MAX_AGE_SEC = 24 * 3600


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="cor1x-user-session")


def _verify_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="cor1x-email-verify")


# ── Session cookie ───────────────────────────────────────────────────


def issue_session(user_id: str) -> str:
    return _session_serializer().dumps({"uid": user_id})


def decode_session(token: str) -> str | None:
    """Return the user_id claimed by a session cookie, or None if invalid."""
    try:
        payload: Any = _session_serializer().loads(token, max_age=SESSION_MAX_AGE_SEC)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    uid = payload.get("uid")
    return uid if isinstance(uid, str) else None


# Cookie cross-site policy — driven by `cross_site_cookies`, NOT DEBUG.
#
# On any HTTPS deployment where the frontend and backend are different sites
# (e.g. two *.up.railway.app subdomains — up.railway.app is a public suffix,
# so each subdomain is its own site), a SameSite=lax cookie is never sent on
# the cross-site frontend→API request. Set CROSS_SITE_COOKIES=true there so
# the cookies are `SameSite=None; Secure` and flow over HTTPS.
#
# Local http://localhost dev leaves it false: SameSite=None requires Secure,
# and Secure cookies are dropped over plain http, so dev uses lax + insecure.
# This is independent of DEBUG so a testing env can keep DEBUG=true (OTP stub,
# relaxed limits) while still issuing working cross-site cookies.
def _cookie_policy() -> tuple[str, bool]:
    if settings.cross_site_cookies:
        return "none", True
    return "lax", False


def set_session_cookie(response: Response, user_id: str) -> None:
    samesite, secure = _cookie_policy()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=issue_session(user_id),
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


# ── Email verification token ─────────────────────────────────────────


def issue_verify_token(user_id: str) -> str:
    return _verify_serializer().dumps({"uid": user_id})


def decode_verify_token(token: str) -> str | None:
    try:
        payload: Any = _verify_serializer().loads(
            token, max_age=VERIFY_TOKEN_MAX_AGE_SEC
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    uid = payload.get("uid")
    return uid if isinstance(uid, str) else None
