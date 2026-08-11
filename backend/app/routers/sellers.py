from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.identity import Identity
from app.models.seller import Seller, SellerOnboardingPath
from app.models.user import User, UserStatus, UserType
from app.schemas.seller import SellerCreate, SellerCreated

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.post("", response_model=SellerCreated, response_model_by_alias=True, status_code=201)
async def create_seller(
    payload: SellerCreate, db: AsyncSession = Depends(get_db)
) -> SellerCreated:
    # Reject duplicate GSTIN early with a clear message
    if payload.gstin:
        existing = await db.scalar(select(Seller).where(Seller.gstin == payload.gstin))
        if existing:
            raise HTTPException(status_code=409, detail="This GSTIN is already registered")

    # 1. Create user
    user = User(user_type=UserType.seller, status=UserStatus.signed_up)
    db.add(user)
    await db.flush()

    # 2. Create identity for the verified mobile
    identity = Identity(
        user_id=user.id,
        value=payload.mobile,
        verified_at=datetime.now(tz=timezone.utc),
    )
    db.add(identity)

    # 3. Create seller row
    seller = Seller(
        user_id=user.id,
        onboarding_path=SellerOnboardingPath(payload.onboarding_path),
        gstin=payload.gstin,
        pan=payload.pan,
        company_name=payload.company_name,
        business_type=payload.business_type,
        nature_of_business=payload.nature_of_business,
        owner_name=payload.owner_name,
        building=payload.building,
        pincode=payload.pincode,
        city=payload.city,
        district=payload.district,
        state=payload.state,
        country=payload.country,
    )
    db.add(seller)

    # 4. Mark user as profile_complete (verified is set later by admin)
    user.status = UserStatus.profile_complete

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate mobile or GSTIN") from e

    return SellerCreated(id=str(seller.id), status=user.status.value)
