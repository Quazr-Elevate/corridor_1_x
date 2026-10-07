"""Profile section saves — primary (personal), business (free-text), bank."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.schemas.profile import (
    BankDetailsIn,
    BusinessDetails,
    PrimaryDetails,
    ProfileSectionSaved,
)

router = APIRouter(prefix="/profile", tags=["profile"])


# ── Completion helpers ───────────────────────────────────────────────


def _primary_complete(p: Profile | None) -> bool:
    return bool(
        p
        and p.full_name
        and p.address_line
        and p.city
        and p.state
        and p.pincode
    )


def _business_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and (bp.business_type or bp.nature_of_business))


def _bank_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.bank_account_number and bp.bank_ifsc and bp.bank_holder_name)


async def _maybe_verify_user(user: User, db: AsyncSession) -> None:
    """Bump status → 'verified' the first time all three sections are done."""
    await db.flush()
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    all_done = (
        _primary_complete(profile)
        and _business_complete(business)
        and _bank_complete(business)
    )
    if all_done and user.status != UserStatus.verified:
        user.status = UserStatus.verified


# ── Primary details ──────────────────────────────────────────────────


@router.post("/primary", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_primary(
    payload: PrimaryDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        profile = Profile(user_id=user.id, full_name=payload.full_name)
        db.add(profile)
    profile.full_name = payload.full_name
    profile.address_line = payload.address_line
    profile.city = payload.city
    profile.state = payload.state
    profile.pincode = payload.pincode
    if payload.country:
        profile.country = payload.country
    profile.website_url = payload.website_url
    profile.google_business_url = payload.google_business_url
    profile.facebook_url = payload.facebook_url

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()


# ── Business details ─────────────────────────────────────────────────


@router.post("/business", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_business(
    payload: BusinessDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if business is None:
        business = BusinessProfile(user_id=user.id)
        db.add(business)
    business.business_type = payload.business_type
    business.nature_of_business = payload.nature_of_business
    business.udyam = payload.udyam

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()


# ── Bank details ─────────────────────────────────────────────────────


@router.post("/bank", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_bank(
    payload: BankDetailsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if business is None:
        business = BusinessProfile(user_id=user.id)
        db.add(business)

    # IFSC must be verified via /verify/ifsc first — that call sets bank_ifsc
    # + ifsc_verified_at atomically. Here we only accept the same IFSC that's
    # already verified, so the client can't sneak in an unverified code.
    submitted_ifsc = payload.ifsc.strip().upper()
    if submitted_ifsc != (business.bank_ifsc or "") or business.ifsc_verified_at is None:
        raise HTTPException(
            status_code=400,
            detail="IFSC was not verified. Click Verify on the IFSC field first.",
        )

    # Bank account number uniqueness — an account belongs to one holder.
    account_number = payload.account_number.strip()
    dup = await db.scalar(
        select(BusinessProfile.user_id).where(
            BusinessProfile.bank_account_number == account_number,
            BusinessProfile.user_id != user.id,
        )
    )
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail="This bank account is already registered to another account",
        )
    business.bank_account_number = account_number
    business.bank_holder_name = payload.holder_name
    if payload.branch_name is not None:
        business.bank_branch_name = payload.branch_name
    if payload.bank_name is not None:
        business.bank_name = payload.bank_name

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()
