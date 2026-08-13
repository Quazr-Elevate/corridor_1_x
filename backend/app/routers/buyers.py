from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.buyer import Buyer
from app.models.identity import Identity
from app.models.user import User, UserStatus, UserType
from app.schemas.buyer import BuyerCreate, BuyerCreated

router = APIRouter(prefix="/buyers", tags=["buyers"])


@router.post("", response_model=BuyerCreated, response_model_by_alias=True, status_code=201)
async def create_buyer(
    payload: BuyerCreate, db: AsyncSession = Depends(get_db)
) -> BuyerCreated:
    # 1. Create user (buyers skip profile_complete per the phase-1 doc — they
    #    go from signed_up straight to verified after admin review).
    user = User(user_type=UserType.buyer, status=UserStatus.signed_up)
    db.add(user)
    await db.flush()

    # 2. Identity for the verified mobile
    identity = Identity(
        user_id=user.id,
        value=payload.mobile,
        verified_at=datetime.now(tz=timezone.utc),
    )
    db.add(identity)

    # 3. Buyer profile row
    buyer = Buyer(
        user_id=user.id,
        full_name=payload.full_name,
        company_name=payload.company_name,
        country=payload.country,
        city=payload.city,
    )
    db.add(buyer)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate mobile") from e

    return BuyerCreated(id=str(buyer.id), status=user.status.value)
