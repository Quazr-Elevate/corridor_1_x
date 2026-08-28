from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.business_profile import BusinessProfile
from app.providers.gstin import lookup_gstin
from app.schemas.gstin import GstinLookup

router = APIRouter(prefix="/gstin", tags=["gstin"])


@router.get("/{gstin}", response_model=GstinLookup, response_model_by_alias=True)
async def get_gstin(gstin: str, db: AsyncSession = Depends(get_db)) -> GstinLookup:
    clean = gstin.strip().upper()

    # Reject duplicates upfront — gives immediate feedback at the Verify step
    # and avoids burning a paid Masters India API call for a GSTIN that's
    # already on file.
    existing = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.gstin == clean)
    )
    if existing:
        raise HTTPException(status_code=409, detail="This GSTIN is already registered")

    try:
        return await lookup_gstin(clean)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
