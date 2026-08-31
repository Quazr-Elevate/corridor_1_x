"""User session cookies — signed JWT-ish tokens for /login and /signup.

Two cookie kinds:

1. ``cor1x_session``       — set on login and on successful /auth/signup.
                             Carries the user's UUID. Verified on every
                             authenticated request via `get_current_user`
                             (deps.py) as a fallback to the X-User-Id header.

2. ``cor1x_verified_phone`` — set after OTP verification on a mobile that
                              doesn't yet have an account. Carries the
                              mobile number for the next 10 minutes so
                              /auth/signup can finalize the account.

Both are HttpOnly, SameSite=lax, and Secure when not in debug mode. Signed
with `settings.session_secret` via itsdangerous URLSafeTimedSerializer.
"""
from __future__ import annotations

from typing import Any

from fastapi import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

SESSION_COOKIE = "cor1x_session"
VERIFIED_PHONE_COOKIE = "cor1x_verified_phone"

# Session lives 24h — matches the frontend localStorage expiry the pulled
# commit set up. Verified-phone cookie is much shorter because it's a step
# in the signup flow, not a durable login.
SESSION_MAX_AGE_SEC = 24 * 3600
VERIFIED_PHONE_MAX_AGE_SEC = 10 * 60


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret, salt="cor1x-user-session"
    )


def _verified_phone_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret, salt="cor1x-verified-phone"
    )


# ── Session ──────────────────────────────────────────────────────────


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


# ── Verified-phone bridge ────────────────────────────────────────────


def issue_verified_phone(mobile: str) -> str:
    return _verified_phone_serializer().dumps({"mobile": mobile})


def decode_verified_phone(token: str) -> str | None:
    try:
        payload: Any = _verified_phone_serializer().loads(
            token, max_age=VERIFIED_PHONE_MAX_AGE_SEC
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    mobile = payload.get("mobile")
    return mobile if isinstance(mobile, str) else None


def set_verified_phone_cookie(response: Response, mobile: str) -> None:
    samesite, secure = _cookie_policy()
    response.set_cookie(
        key=VERIFIED_PHONE_COOKIE,
        value=issue_verified_phone(mobile),
        max_age=VERIFIED_PHONE_MAX_AGE_SEC,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )


def clear_verified_phone_cookie(response: Response) -> None:
    response.delete_cookie(VERIFIED_PHONE_COOKIE, path="/")
