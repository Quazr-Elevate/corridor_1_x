"""Atomic field verification — OTP + write happen in the same call.

Two shapes of verification here:

  1. Contact verification (`/verify/contact`): user has already called
     /otp/send + /otp/verify with the code. This endpoint re-checks the
     OTP with the provider, then writes value + *_verified_at onto the
     profile row in one commit. No trust in a "verified?" boolean the
     client could flip.

  2. Business identifier verification (`/verify/gstin`, `/verify/pan`,
     `/verify/ifsc`): no OTP — instead we call the corresponding provider
     (Masters India / Razorpay). If the lookup succeeds we write the
     value and stamp *_verified_at, plus the provider-returned metadata
     (company name, bank / branch, etc.) that the user will confirm on
     the profile screen.

The regular /profile/{primary,business,bank} save endpoints treat these
fields as read-only. That's the mechanism enforcing "you can't POST an
unverified GSTIN or email" — the save endpoint simply ignores the field
if it isn't already verified via one of the endpoints below.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile, OnboardingPath
from app.models.profile import Profile
from app.models.user import User
from app.providers.gstin import lookup_gstin
from app.providers.ifsc import IfscNotFound, IfscServiceError, lookup_ifsc
from app.providers.otp import verify_otp
from app.rate_limit import check_otp_rate_limit
from app.schemas.base import CamelModel
from app.schemas.gstin import GstinLookup
from app.validators import EMAIL_REGEX, GSTIN_REGEX, PAN_REGEX, PHONE_REGEX

router = APIRouter(prefix="/verify", tags=["verify"])

# ── Schemas ──────────────────────────────────────────────────────────────────

ContactTarget = Literal["email", "alt_mobile", "alt_email", "business_email"]


class ContactVerifyRequest(CamelModel):
    """POST /verify/contact — OTP verify + write."""

    target: ContactTarget
    value: str
    code: str


class VerifyOk(CamelModel):
    ok: bool = True
    verified_at: datetime


class BusinessIdVerifyRequest(CamelModel):
    """POST /verify/{gstin,pan,ifsc}. The lookup calls out to the provider,
    then writes value + stamp on the caller's business profile in one commit.
    """

    value: str = Field(min_length=1, max_length=20)


class GstinVerified(CamelModel):
    ok: bool = True
    verified_at: datetime
    lookup: GstinLookup


class PanVerified(CamelModel):
    ok: bool = True
    verified_at: datetime
    pan: str
    name: str


class IfscVerified(CamelModel):
    ok: bool = True
    verified_at: datetime
    ifsc: str
    bank: str
    branch: str


# ── Helpers ──────────────────────────────────────────────────────────────────


# One place to know which profile column pair a target maps to. Adding a
# new verifiable contact field is one entry here + one migration column.
_CONTACT_FIELDS: dict[ContactTarget, tuple[str, str, Literal["phone", "email"]]] = {
    "email": ("email", "email_verified_at", "email"),
    "alt_mobile": ("alt_mobile", "alt_mobile_verified_at", "phone"),
    "alt_email": ("alt_email", "alt_email_verified_at", "email"),
    "business_email": ("business_email", "business_email_verified_at", "email"),
}


def _normalize(value: str, channel: Literal["phone", "email"]) -> str:
    v = value.strip()
    return v.lower() if channel == "email" else v


def _validate_shape(value: str, channel: Literal["phone", "email"]) -> None:
    ok = (
        EMAIL_REGEX.match(value)
        if channel == "email"
        else PHONE_REGEX.match(value)
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid email address" if channel == "email"
            else "Enter a valid 10-digit mobile number",
        )


async def _ensure_business(user: User, db: AsyncSession, *, onboarding_path: OnboardingPath, defaults: dict) -> BusinessProfile:
    """Fetch-or-create the caller's business profile row.

    business_profiles.pan/company_name are NOT NULL — creating a row via the
    PAN or GSTIN verify endpoints means we know both up front (PAN from the
    input, company_name filled from the lookup). IFSC verify is only allowed
    once a business row exists (bank fields live on it).
    """
    bp = await db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    if bp is not None:
        return bp
    bp = BusinessProfile(user_id=user.id, onboarding_path=onboarding_path, **defaults)
    db.add(bp)
    await db.flush()
    return bp


# ── Contact verify (email / alt_mobile / alt_email / business_email) ─────────


@router.post("/contact", response_model=VerifyOk, response_model_by_alias=True)
async def verify_contact(
    payload: ContactVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyOk:
    field, stamp, channel = _CONTACT_FIELDS[payload.target]
    value = _normalize(payload.value, channel)
    _validate_shape(value, channel)

    check_otp_rate_limit(value)

    # Uniqueness: primary/business_email + alt_email share the email column;
    # alt_mobile competes with the identities table. Reject if another user
    # owns this value, so contact fields can't shadow someone else's account.
    if channel == "email":
        other = await db.scalar(
            select(Profile.user_id).where(
                (Profile.email == value) | (Profile.business_email == value) | (Profile.alt_email == value),
                Profile.user_id != user.id,
            )
        )
        if other is not None:
            raise HTTPException(status_code=409, detail="This email is already registered to another account")
    else:
        from app.models.identity import Identity

        other = await db.scalar(
            select(Identity.user_id).where(Identity.value == value, Identity.user_id != user.id)
        )
        if other is not None:
            raise HTTPException(status_code=409, detail="This mobile is already registered to another account")

    result = await verify_otp(channel, value, payload.code)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "Incorrect code")

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    now = datetime.now(tz=timezone.utc)
    setattr(profile, field, value)
    setattr(profile, stamp, now)
    await db.commit()
    return VerifyOk(verified_at=now)


# ── GSTIN verify ─────────────────────────────────────────────────────────────


@router.post("/gstin", response_model=GstinVerified, response_model_by_alias=True)
async def verify_gstin(
    payload: BusinessIdVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GstinVerified:
    clean = payload.value.strip().upper()
    if not GSTIN_REGEX.match(clean):
        raise HTTPException(status_code=400, detail="Enter a valid 15-character GSTIN")

    check_otp_rate_limit(f"gstin:{clean}")

    # Duplicate check across every user (this GSTIN can only exist once).
    dup = await db.scalar(
        select(BusinessProfile.user_id).where(
            BusinessProfile.gstin == clean, BusinessProfile.user_id != user.id
        )
    )
    if dup is not None:
        raise HTTPException(status_code=409, detail="This GSTIN is already registered")

    try:
        lookup = await lookup_gstin(clean)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    bp = await _ensure_business(
        user, db,
        onboarding_path=OnboardingPath.gstin,
        defaults={"gstin": clean, "pan": lookup.pan, "company_name": lookup.legal_name},
    )
    now = datetime.now(tz=timezone.utc)
    bp.gstin = clean
    bp.gstin_verified_at = now
    # PAN is derived from GSTIN chars 3–12 and is government-issued, so we
    # stamp pan_verified_at from the same lookup — no separate PAN call needed.
    bp.pan = lookup.pan
    bp.pan_verified_at = now
    if not bp.company_name:
        bp.company_name = lookup.legal_name
    if not bp.business_type and lookup.business_type:
        bp.business_type = lookup.business_type
    if not bp.nature_of_business and lookup.nature_of_business:
        bp.nature_of_business = lookup.nature_of_business
    await db.commit()
    return GstinVerified(verified_at=now, lookup=lookup)


# ── PAN verify (stub — real Masters India PAN wire is TODO) ──────────────────

_PAN_STUB_NAMES: dict[str, str] = {
    "A": "Aarav Sharma", "B": "Bharat Iyer", "C": "Chetan Nair", "D": "Devang Patel",
    "E": "Ekansh Rao", "F": "Farhan Khan", "G": "Gaurav Menon", "H": "Harsh Verma",
    "I": "Ishaan Rao", "J": "Jayesh Bhat", "K": "Karthik Reddy", "L": "Lakshay Singh",
    "M": "Manish Gupta", "N": "Nikhil Desai", "O": "Om Prakash", "P": "Pranav Kulkarni",
    "Q": "Qadir Sheikh", "R": "Rahul Joshi", "S": "Siddharth Mehta", "T": "Tanmay Shah",
    "U": "Utkarsh Rai", "V": "Vikram Nair", "W": "Wasim Ali", "X": "Xavier D'Souza",
    "Y": "Yash Agarwal", "Z": "Zeeshan Malik",
}


@router.post("/pan", response_model=PanVerified, response_model_by_alias=True)
async def verify_pan(
    payload: BusinessIdVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PanVerified:
    clean = payload.value.strip().upper()
    if not PAN_REGEX.match(clean):
        raise HTTPException(status_code=400, detail="Enter a valid 10-character PAN")

    check_otp_rate_limit(f"pan:{clean}")

    dup = await db.scalar(
        select(BusinessProfile.user_id).where(
            BusinessProfile.pan == clean, BusinessProfile.user_id != user.id
        )
    )
    if dup is not None:
        raise HTTPException(status_code=409, detail="This PAN is already registered")

    # TODO(masters_india_pan): swap this for the real Masters India PAN API
    # once the endpoint is enabled on the account. Signature stays the same.
    name = _PAN_STUB_NAMES.get(clean[0], "Aarav Sharma")

    bp = await _ensure_business(
        user, db,
        onboarding_path=OnboardingPath.pan,
        # company_name is NOT NULL — for a PAN-only onboarding path we seed it
        # with the resolved name; the user can edit it on the business form.
        defaults={"pan": clean, "company_name": name},
    )
    now = datetime.now(tz=timezone.utc)
    bp.pan = clean
    bp.pan_verified_at = now
    if not bp.company_name:
        bp.company_name = name
    await db.commit()
    return PanVerified(verified_at=now, pan=clean, name=name)


# ── IFSC verify ──────────────────────────────────────────────────────────────


@router.post("/ifsc", response_model=IfscVerified, response_model_by_alias=True)
async def verify_ifsc(
    payload: BusinessIdVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IfscVerified:
    clean = payload.value.strip().upper()
    check_otp_rate_limit(f"ifsc:{clean}")

    try:
        data = await lookup_ifsc(clean)
    except IfscNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except IfscServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    bp = await db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    if bp is None:
        raise HTTPException(
            status_code=409,
            detail="Fill Business details (verify GSTIN or PAN) before Bank details",
        )
    now = datetime.now(tz=timezone.utc)
    bp.bank_ifsc = clean
    bp.ifsc_verified_at = now
    # Fill bank/branch names from the lookup so the Bank form pre-populates.
    if data.get("bank"):
        bp.bank_name = data["bank"]
    if data.get("branch"):
        bp.bank_branch_name = data["branch"]
    await db.commit()
    return IfscVerified(verified_at=now, ifsc=clean, bank=data.get("bank", ""), branch=data.get("branch", ""))
