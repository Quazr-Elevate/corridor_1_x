from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.models.user import User, UserStatus
from app.providers.otp import verify_otp
from app.schemas.auth import AuthVerifyRequest, AuthVerifyResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify")
async def verify(payload: AuthVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Unified sign-in / sign-up. Verifies the OTP, then:
    - returns 200 with is_new=false if the mobile already has an account
    - creates a User + verified Identity and returns 201 with is_new=true
      if it's a fresh mobile

    Role (buyer vs seller) is derived — a user becomes a seller by adding
    their first product. No column stored for it.
    """
    otp_result = await verify_otp("phone", payload.mobile, payload.code)
    if not otp_result.ok:
        raise HTTPException(status_code=400, detail=otp_result.error or "Verification failed")

    mobile = payload.mobile.strip()
    existing = await db.scalar(select(Identity).where(Identity.value == mobile))

    if existing:
        body = AuthVerifyResponse(
            user_id=str(existing.user_id),
            is_new=False,
            # TODO: check if profile row exists to know whether profile setup
            # is still needed. For now assume returning users have completed it.
            needs_profile=False,
        )
        return JSONResponse(status_code=200, content=body.model_dump(by_alias=True))

    user = User(status=UserStatus.signed_up)
    db.add(user)
    await db.flush()

    identity = Identity(
        user_id=user.id,
        value=mobile,
        verified_at=datetime.now(tz=timezone.utc),
    )
    db.add(identity)
    await db.commit()

    body = AuthVerifyResponse(
        user_id=str(user.id),
        is_new=True,
        needs_profile=True,
    )
    return JSONResponse(status_code=201, content=body.model_dump(by_alias=True))
