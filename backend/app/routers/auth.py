"""Signup + logout.

Login has no dedicated endpoint — it happens as a side effect of
/otp/verify when the mobile is already registered (cookie set there,
frontend redirects to dashboard).

Signup is a two-legged flow:
  1. /otp/send + /otp/verify establish "this phone owner is real" and
     drop a cor1x_verified_phone cookie.
  2. /auth/signup here reads that cookie, takes the full_name + email +
     consent from the form, and creates User + Identity + Profile in one
     transaction. The cookie is swapped for a durable cor1x_session.

The old /auth/verify endpoint is kept as a shim that just proxies to
/otp/verify so pulled frontend code that still calls it keeps working.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.schemas.auth import SignupRequest, SignupResponse
from app.user_session import (
    SESSION_COOKIE,
    VERIFIED_PHONE_COOKIE,
    clear_session_cookie,
    clear_verified_phone_cookie,
    decode_verified_phone,
    set_session_cookie,
)
from app.validators import PERSON_NAME_REGEX

router = APIRouter(prefix="/auth", tags=["auth"])

# Bump when the Privacy Policy / Terms text materially changes.
CURRENT_CONSENT_VERSION = "T-2026-08-29"


@router.post(
    "/signup",
    response_model=SignupResponse,
    response_model_by_alias=True,
    status_code=201,
)
async def signup(
    payload: SignupRequest,
    response: Response,
    cor1x_verified_phone: str | None = Cookie(default=None, alias=VERIFIED_PHONE_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> SignupResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=400,
            detail="You must accept the Terms and Privacy Policy to continue",
        )

    if not cor1x_verified_phone:
        raise HTTPException(
            status_code=401,
            detail="Phone not verified. Restart the OTP step.",
        )
    mobile = decode_verified_phone(cor1x_verified_phone)
    if not mobile:
        raise HTTPException(
            status_code=401,
            detail="Verification expired. Restart the OTP step.",
        )

    full_name = payload.full_name.strip()
    if not PERSON_NAME_REGEX.match(full_name):
        raise HTTPException(
            status_code=400,
            detail="Full name must be letters, spaces, hyphens, apostrophes, or periods only",
        )

    # Defensive re-check — race with a concurrent signup on the same phone.
    existing = await db.scalar(select(Identity).where(Identity.value == mobile))
    if existing is not None:
        # Someone finished signup between the OTP verify and this call.
        # Sign them in instead of erroring.
        set_session_cookie(response, str(existing.user_id))
        clear_verified_phone_cookie(response)
        return SignupResponse(user_id=str(existing.user_id), is_new=False)

    user = User(status=UserStatus.signed_up)
    db.add(user)
    await db.flush()

    identity = Identity(
        user_id=user.id,
        value=mobile,
        verified_at=datetime.now(tz=timezone.utc),
    )
    db.add(identity)

    # Email is intentionally omitted — user adds it from the profile page
    # via /verify/email, which sets email + email_verified_at atomically.
    profile = Profile(
        user_id=user.id,
        full_name=full_name,
        consent_at=datetime.now(tz=timezone.utc),
        consent_version=payload.consent_version or CURRENT_CONSENT_VERSION,
    )
    db.add(profile)

    await db.commit()

    set_session_cookie(response, str(user.id))
    clear_verified_phone_cookie(response)
    return SignupResponse(user_id=str(user.id))


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    """Clear the session cookie. Idempotent — safe to call while signed out."""
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/session")
async def whoami(
    cor1x_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str | None]:
    """Lightweight probe used by the frontend middleware to decide whether
    to redirect an unauthenticated request. Returns {userId: ...} on hit,
    {userId: null} otherwise. Doesn't hit the DB — just checks signature.
    """
    from app.user_session import decode_session

    uid = decode_session(cor1x_session) if cor1x_session else None
    # camelCase key so it matches the CamelModel-serialized envelope used
    # by every other endpoint the frontend consumes.
    return {"userId": uid}
