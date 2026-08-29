from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.schemas.profile import (
    BankDetailsIn,
    BusinessDetails,
    PrimaryDetails,
    ProfileSectionSaved,
    RegulatoryDetails,
)
from app.validators import GSTIN_REGEX, PAN_REGEX

router = APIRouter(prefix="/profile", tags=["profile"])


# ── Completion / verified-status helpers ─────────────────────────────────────


def _primary_complete(p: Profile | None) -> bool:
    return bool(
        p
        and p.full_name
        and p.email
        and p.address_line
        and p.city
        and p.state
        and p.pincode
    )


def _business_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.pan and bp.company_name)


def _bank_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.bank_account_number and bp.bank_ifsc and bp.bank_holder_name)


async def _has_products(user_id, db: AsyncSession) -> bool:
    return bool(
        await db.scalar(
            select(func.count(Product.id)).where(Product.user_id == user_id)
        )
    )


async def _maybe_verify_user(user: User, db: AsyncSession) -> None:
    """Bump `users.status` to 'verified' the first time all three required
    sections (Primary + Business + Bank) are complete. Adding a product does
    not gate this — role is a separate axis (a verified buyer without products
    is fine; a verified seller has products *and* all three sections)."""
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


# ── Primary details ──────────────────────────────────────────────────────────


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
    # NOTE: email / alt_mobile / alt_email / business_email are intentionally
    # NOT written here. Those fields are set atomically by /verify/contact
    # after OTP verification. Ignoring them on this endpoint is the mechanism
    # that stops unverified addresses from reaching the DB.

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()


# ── Business details ─────────────────────────────────────────────────────────


@router.post("/business", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_business(
    payload: BusinessDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    pan = payload.pan.strip().upper()
    if not PAN_REGEX.match(pan):
        raise HTTPException(status_code=400, detail="Enter a valid 10-character PAN")
    gstin = payload.gstin.strip().upper() if payload.gstin else None
    if gstin and not GSTIN_REGEX.match(gstin):
        raise HTTPException(status_code=400, detail="Enter a valid 15-character GSTIN")

    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    # GSTIN + PAN must go through /verify/{gstin,pan} first. That's the
    # endpoint that actually calls Masters India and stamps *_verified_at.
    # This save endpoint only accepts values whose verified stamps already
    # exist and match — same value, or unchanged. Otherwise the client is
    # trying to bypass verification and we reject.
    if business is None:
        raise HTTPException(
            status_code=409,
            detail="Verify GSTIN or PAN first — use the Verify button on the field",
        )
    if pan != (business.pan or "") and (
        business.pan_verified_at is None or (business.pan or "") != pan
    ):
        raise HTTPException(
            status_code=400,
            detail="PAN was not verified. Click Verify on the PAN field first.",
        )
    if gstin and gstin != (business.gstin or "") and (
        business.gstin_verified_at is None or (business.gstin or "") != gstin
    ):
        raise HTTPException(
            status_code=400,
            detail="GSTIN was not verified. Click Verify on the GSTIN field first.",
        )
    # Only free-text metadata is writable via this endpoint.
    business.company_name = payload.company_name
    if payload.business_type is not None:
        business.business_type = payload.business_type
    if payload.nature_of_business is not None:
        business.nature_of_business = payload.nature_of_business

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()


# ── Bank details ─────────────────────────────────────────────────────────────


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
        # Bank lives on business_profiles; we need the KYB row first.
        raise HTTPException(
            status_code=409,
            detail="Fill Business details first before adding Bank details",
        )
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
    # Two different marketplace users claiming the same account is a red
    # flag (payout collision or account takeover attempt); reject with a
    # clear 409 rather than silently allowing the shadow.
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


# ── Regulatory extras (udyam/aadhaar/tan) ────────────────────────────────────


@router.post("/regulatory", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_regulatory(
    payload: RegulatoryDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if business is None:
        raise HTTPException(
            status_code=409,
            detail="Fill Business details first before adding regulatory IDs",
        )
    business.udyam = payload.udyam
    business.aadhaar = payload.aadhaar
    business.tan = payload.tan
    await db.commit()
    return ProfileSectionSaved()


# ── Backwards-compat alias — legacy /profile/seller path used by the pulled
#     frontend still routes to the same handler. Safe to remove once the
#     dashboard drops the old endpoint name.
# ────────────────────────────────────────────────────────────────────────────
router.add_api_route(
    "/seller",
    save_regulatory,
    methods=["POST"],
    response_model=ProfileSectionSaved,
    response_model_by_alias=True,
    name="save_regulatory_alias",
)
