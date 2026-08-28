from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.models.profile import Profile
from app.providers.otp import send_otp, verify_otp
from app.schemas.otp import OtpSendRequest, OtpSendResponse, OtpVerifyRequest, OtpVerifyResponse

router = APIRouter(prefix="/otp", tags=["otp"])


@router.post("/send", response_model=OtpSendResponse, response_model_by_alias=True)
async def send(
    payload: OtpSendRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> OtpSendResponse:
    """Send an OTP via SMS (phone channel, MSG91 or stub) or email (stub).

    Signup / signin (no X-User-Id): duplicate-mobile is fine — the unified
    /auth/verify flow uses the same OTP for both. Alt-mobile OTP (X-User-Id
    present): we reject if the target phone already belongs to another user's
    primary identity, so alt fields can't shadow someone else's real account.
    """
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


@router.post("/verify", response_model=OtpVerifyResponse, response_model_by_alias=True)
async def verify(payload: OtpVerifyRequest) -> OtpVerifyResponse:
    value = payload.email if payload.channel == "email" else payload.mobile
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"Missing {'email' if payload.channel == 'email' else 'mobile'} in verify payload",
        )
    result = await verify_otp(payload.channel, value, payload.code)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "Verification failed")
    return result
