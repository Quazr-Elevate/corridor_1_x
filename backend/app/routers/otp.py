from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.providers.otp import send_otp, verify_otp
from app.schemas.otp import OtpSendRequest, OtpSendResponse, OtpVerifyRequest, OtpVerifyResponse

router = APIRouter(prefix="/otp", tags=["otp"])


@router.post("/send", response_model=OtpSendResponse, response_model_by_alias=True)
async def send(
    payload: OtpSendRequest, db: AsyncSession = Depends(get_db)
) -> OtpSendResponse:
    if payload.channel != "phone":
        raise HTTPException(status_code=400, detail="Only phone OTP is supported")

    # Reject if this mobile is already registered — don't burn an SMS on a
    # number that already has an account. When login is added later, this
    # check will move behind a purpose=signup flag.
    existing = await db.scalar(
        select(Identity).where(Identity.value == payload.value.strip())
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="This mobile number is already registered"
        )

    try:
        return await send_otp(payload.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/verify", response_model=OtpVerifyResponse, response_model_by_alias=True)
async def verify(payload: OtpVerifyRequest) -> OtpVerifyResponse:
    result = await verify_otp(payload.mobile, payload.code)
    if not result.ok:
        # Return the failure body with a 400 so the frontend surfaces the error.
        raise HTTPException(status_code=400, detail=result.error or "Verification failed")
    return result
