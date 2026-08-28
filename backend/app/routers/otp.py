"""OTP send + verify.

`/otp/verify` is the pivot for both login and signup:

  - If the mobile is already registered → set the session cookie now
    (this WAS a login attempt) and respond {isNew: false, userId}.
  - If the mobile is new → set a short-lived cor1x_verified_phone cookie
    so /auth/signup can pick it up when the user finishes the form,
    and respond {isNew: true}.

No DB row is created here on the new-user path. That happens atomically
in /auth/signup once the user submits full_name + email + consent.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.models.profile import Profile
from app.providers.otp import send_otp, verify_otp
from app.rate_limit import check_otp_rate_limit
from app.schemas.otp import (
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
)
from app.user_session import (
    set_session_cookie,
    set_verified_phone_cookie,
)

router = APIRouter(prefix="/otp", tags=["otp"])


@router.post("/send", response_model=OtpSendResponse, response_model_by_alias=True)
async def send(
    payload: OtpSendRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> OtpSendResponse:
    """Send an OTP via SMS (phone channel, MSG91 or stub) or email (stub).

    Signup / signin (no X-User-Id): duplicate-mobile is fine — the unified
    flow uses the same OTP for both. Alt-mobile OTP (X-User-Id present):
    reject if the target phone already belongs to another user's primary
    identity, so alt fields can't shadow someone else's real account.
    """
    # Rate limit — no more than 3 sends per identifier per hour.
    check_otp_rate_limit(payload.value)

    if x_user_id:
        try:
            requester = UUID(x_user_id)
        except ValueError:
            requester = None
        if requester is not None:
            if payload.channel == "phone":
                owner = await db.scalar(
                    select(Identity.user_id).where(
                        Identity.value == payload.value.strip()
                    )
                )
                if owner is not None and owner != requester:
                    raise HTTPException(
                        status_code=409,
                        detail="This mobile is already registered to another account",
                    )
            elif payload.channel == "email":
                normalized = payload.value.strip().lower()
                owner = await db.scalar(
                    select(Profile.user_id).where(Profile.email == normalized)
                )
                if owner is not None and owner != requester:
                    raise HTTPException(
                        status_code=409,
                        detail="This email is already registered to another account",
                    )
    try:
        return await send_otp(payload.channel, payload.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/verify",
    response_model=OtpVerifyResponse,
    response_model_by_alias=True,
)
async def verify(
    payload: OtpVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> OtpVerifyResponse:
    """Verify an OTP + decide login vs signup based on identity existence.

    Login (mobile already has an identity): set the session cookie now,
    return {ok, isNew: false, userId}.

    Signup (fresh mobile): set the verified-phone cookie (10-min TTL) so
    /auth/signup can complete the account creation, return {ok, isNew: true}.

    Email OTP verify (used for alt-email confirm) still just returns {ok}
    without touching cookies — that's a form-level action, not sign-in.
    """
    value = payload.email if payload.channel == "email" else payload.mobile
    if not value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Missing {'email' if payload.channel == 'email' else 'mobile'} "
                "in verify payload"
            ),
        )
    result = await verify_otp(payload.channel, value, payload.code)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "Verification failed")

    # Only phone OTPs participate in the session bridge — email OTPs are
    # confirmations for alt fields on the profile.
    if payload.channel == "phone" and payload.mobile:
        mobile = payload.mobile.strip()
        existing = await db.scalar(
            select(Identity).where(Identity.value == mobile)
        )
        if existing is not None:
            # Login path — set the durable session cookie now.
            set_session_cookie(response, str(existing.user_id))
            return OtpVerifyResponse(
                ok=True,
                is_new=False,
                user_id=str(existing.user_id),
            )
        # Signup path — bridge cookie carries the phone into /auth/signup.
        set_verified_phone_cookie(response, mobile)
        return OtpVerifyResponse(ok=True, is_new=True)

    return result
