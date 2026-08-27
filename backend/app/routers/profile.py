from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.bank_details import BankDetails
from app.models.buyer import Buyer
from app.models.seller import Seller, SellerOnboardingPath
from app.models.user import User, UserStatus
from app.schemas.profile import (
    BankDetailsIn,
    BusinessDetails,
    PrimaryDetails,
    ProfileSectionSaved,
    SellerDetails,
)
from app.validators import GSTIN_REGEX, PAN_REGEX

router = APIRouter(prefix="/profile", tags=["profile"])


# ── Completion / verified-status helpers ─────────────────────────────────────


def _primary_complete(b: Buyer | None) -> bool:
    return bool(
        b
        and b.full_name
        and b.email
        and b.address_line
        and b.city
        and b.state
        and b.pincode
    )


def _business_complete(s: Seller | None) -> bool:
    return bool(s and s.pan and s.company_name)


def _bank_complete(bd: BankDetails | None) -> bool:
    return bool(bd and bd.account_number and bd.ifsc and bd.holder_name)


async def _maybe_verify_user(user: User, db: AsyncSession) -> None:
    """Bump user.status to 'verified' the first time all three required
    sections (Primary + Business + Bank) are complete. Adding a product is
    a separate promotion that flips user_type from buyer to seller.
    """
    await db.flush()  # make any staged writes visible to the queries below
    buyer = await db.scalar(select(Buyer).where(Buyer.user_id == user.id))
    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    bank = await db.scalar(select(BankDetails).where(BankDetails.user_id == user.id))
    all_done = _primary_complete(buyer) and _business_complete(seller) and _bank_complete(bank)
    if all_done and user.status != UserStatus.verified:
        user.status = UserStatus.verified


# ── Primary details ──────────────────────────────────────────────────────────


@router.post("/primary", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_primary(
    payload: PrimaryDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    buyer = await db.scalar(select(Buyer).where(Buyer.user_id == user.id))
    if buyer is None:
        buyer = Buyer(user_id=user.id, full_name=payload.full_name)
        db.add(buyer)
    buyer.full_name = payload.full_name
    buyer.email = payload.email
    buyer.address_line = payload.address_line
    buyer.city = payload.city
    buyer.state = payload.state
    buyer.pincode = payload.pincode
    buyer.alt_mobile = payload.alt_mobile
    buyer.alt_email = payload.alt_email
    buyer.business_email = payload.business_email
    buyer.website_url = payload.website_url
    buyer.google_business_url = payload.google_business_url
    buyer.facebook_url = payload.facebook_url

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

    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        # Seller row needs some NOT NULL columns (owner_name, pincode, city, state).
        # Backfill from buyers primary details if present; placeholder otherwise.
        buyer = await db.scalar(select(Buyer).where(Buyer.user_id == user.id))
        seller = Seller(
            user_id=user.id,
            onboarding_path=SellerOnboardingPath.gstin if gstin else SellerOnboardingPath.pan,
            gstin=gstin,
            pan=pan,
            company_name=payload.company_name,
            owner_name=(buyer.full_name if buyer else "—"),
            pincode=(buyer.pincode if buyer and buyer.pincode else "000000"),
            city=(buyer.city if buyer and buyer.city else "—"),
            state=(buyer.state if buyer and buyer.state else "—"),
            country=(buyer.country if buyer and buyer.country else "India"),
        )
        db.add(seller)
    else:
        seller.gstin = gstin
        seller.pan = pan
        seller.company_name = payload.company_name

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
    bank = await db.scalar(select(BankDetails).where(BankDetails.user_id == user.id))
    if bank is None:
        bank = BankDetails(
            user_id=user.id,
            account_number=payload.account_number,
            ifsc=payload.ifsc.upper(),
            holder_name=payload.holder_name,
            branch_name=payload.branch_name,
            bank_name=payload.bank_name,
        )
        db.add(bank)
    else:
        bank.account_number = payload.account_number
        bank.ifsc = payload.ifsc.upper()
        bank.holder_name = payload.holder_name
        bank.branch_name = payload.branch_name
        bank.bank_name = payload.bank_name

    await _maybe_verify_user(user, db)
    await db.commit()
    return ProfileSectionSaved()


# ── Seller details (udyam/aadhaar/tan) ───────────────────────────────────────


@router.post("/seller", response_model=ProfileSectionSaved, response_model_by_alias=True)
async def save_seller(
    payload: SellerDetails,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSectionSaved:
    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        raise HTTPException(
            status_code=409,
            detail="Fill Business details first before adding Seller details",
        )
    seller.udyam = payload.udyam
    seller.aadhaar = payload.aadhaar
    seller.tan = payload.tan
    await db.commit()
    return ProfileSectionSaved()
