"""3-step onboarding wizard, mirrors Tridge's Company / Contact / Business flow.

Endpoints are additive: the wizard is free to call them in any order and any
number of times. Once all three sections are filled, ``onboarded_at`` is
stamped on the business_profile row and the frontend moves the user to the
dashboard.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.profile import Profile
from app.models.user import User
from app.schemas.onboarding import (
    BusinessProfileIn,
    CompanyInfoIn,
    OnboardingSaved,
    OnboardingStatus,
    PrimaryContactIn,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── Section-completeness helpers ─────────────────────────────────────


def _company_info_done(bp: BusinessProfile | None) -> bool:
    return bool(
        bp
        and bp.legal_name
        and bp.industry
        and bp.operating_countries
    )


def _primary_contact_done(p: Profile | None) -> bool:
    return bool(p and p.full_name and p.position)


def _business_profile_done(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.trade_position)


async def _load_status(user: User, db: AsyncSession) -> OnboardingStatus:
    # One round-trip pulls both relationships. Railway Postgres is remote so
    # each query costs ~200ms; halving that matters on the onboarding page
    # which fires /me and /onboarding/status in parallel on every visit.
    row = await db.execute(
        select(User)
        .options(
            joinedload(User.profile),
            joinedload(User.business_profile),
        )
        .where(User.id == user.id)
    )
    hydrated = row.scalar_one()
    profile = hydrated.profile
    business = hydrated.business_profile
    return OnboardingStatus(
        company_info_done=_company_info_done(business),
        primary_contact_done=_primary_contact_done(profile),
        business_profile_done=_business_profile_done(business),
        onboarded_at=business.onboarded_at.isoformat() if business and business.onboarded_at else None,
    )


async def _maybe_finish(user: User, db: AsyncSession) -> None:
    """Post-save hook — stamp onboarded_at when the wizard is complete.

    The Verified-badge submission used to piggyback on this save hook,
    but it's now a user-initiated action (POST /me/submit-verification
    behind the "Send for verification" button). We no longer flip the
    user's status here — a save is a save, nothing more.
    """
    await db.flush()
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    all_done = (
        _company_info_done(business)
        and _primary_contact_done(profile)
        and _business_profile_done(business)
    )
    if all_done and business and business.onboarded_at is None:
        business.onboarded_at = datetime.now(tz=timezone.utc)
    # Silence unused-local warnings — profile is loaded above for the
    # side effect of flushing, same pattern as before.
    _ = profile


# ── Status probe ─────────────────────────────────────────────────────


@router.get("/status", response_model=OnboardingStatus, response_model_by_alias=True)
async def onboarding_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    return await _load_status(user, db)


# ── Step 1 — Company info ────────────────────────────────────────────


@router.post(
    "/company",
    response_model=OnboardingSaved,
    response_model_by_alias=True,
)
async def save_company_info(
    payload: CompanyInfoIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingSaved:
    legal_name = payload.legal_name.strip()
    website_url = payload.website_url.strip() if payload.website_url else None

    # Uniqueness checks — a legal company name or website that another
    # verified-or-pending user has already claimed is almost always a
    # duplicate signup; surface it clearly instead of letting two accounts
    # pretend to be the same business.
    dup_legal = await db.scalar(
        select(BusinessProfile.user_id).where(
            func.lower(BusinessProfile.legal_name) == legal_name.lower(),
            BusinessProfile.user_id != user.id,
        )
    )
    if dup_legal is not None:
        raise HTTPException(
            status_code=409,
            detail="This legal company name is already registered on Cor1x.",
        )
    if website_url:
        dup_site = await db.scalar(
            select(BusinessProfile.user_id).where(
                func.lower(BusinessProfile.website_url) == website_url.lower(),
                BusinessProfile.user_id != user.id,
            )
        )
        if dup_site is not None:
            raise HTTPException(
                status_code=409,
                detail="This website is already linked to another Cor1x account.",
            )

    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if business is None:
        business = BusinessProfile(user_id=user.id)
        db.add(business)
    business.legal_name = legal_name
    business.industry = payload.industry.strip()
    business.operating_countries = [c.strip().upper() for c in payload.operating_countries if c.strip()]
    business.website_url = website_url

    # Keep users.business_name in sync with the legal name — the header + admin
    # UI read it from here for a cheap display without joining business_profiles.
    user.business_name = legal_name

    await _maybe_finish(user, db)
    await db.commit()
    return OnboardingSaved(ok=True, status=await _load_status(user, db))


# ── Step 2 — Primary contact ─────────────────────────────────────────


@router.post(
    "/contact",
    response_model=OnboardingSaved,
    response_model_by_alias=True,
)
async def save_primary_contact(
    payload: PrimaryContactIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingSaved:
    phone = payload.phone.strip() if payload.phone else None

    # Phone uniqueness — compared after normalising away spaces so
    # "+91 98765 43210" and "+919876543210" both collide. Still a soft check,
    # not a DB UNIQUE constraint, so we can relax it later without a migration.
    if phone:
        normalized = _normalize_phone(phone)
        rows = await db.execute(select(Profile.user_id, Profile.phone).where(Profile.phone.is_not(None)))
        for other_uid, other_phone in rows.all():
            if other_uid == user.id:
                continue
            if _normalize_phone(other_phone) == normalized:
                raise HTTPException(
                    status_code=409,
                    detail="This phone number is already registered on Cor1x.",
                )

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        profile = Profile(user_id=user.id, full_name=payload.full_name.strip())
        db.add(profile)
    profile.full_name = payload.full_name.strip()
    profile.phone = phone
    profile.department = payload.department.strip() if payload.department else None
    profile.position = payload.position.strip() if payload.position else None

    await _maybe_finish(user, db)
    await db.commit()
    return OnboardingSaved(ok=True, status=await _load_status(user, db))


def _normalize_phone(raw: str | None) -> str:
    """Strip spaces, dashes, parentheses — keep digits and a leading '+'."""
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isdigit() or ch == "+")


# ── Step 3 — Business profile ────────────────────────────────────────


@router.post(
    "/business",
    response_model=OnboardingSaved,
    response_model_by_alias=True,
)
async def save_business_profile(
    payload: BusinessProfileIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingSaved:
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if business is None:
        business = BusinessProfile(user_id=user.id)
        db.add(business)
    business.trade_position = payload.trade_position.strip()
    business.seller_type = payload.seller_type.strip() if payload.seller_type else None
    business.business_role = payload.business_role.strip() if payload.business_role else None
    business.export_status = payload.export_status.strip() if payload.export_status else None
    business.target_markets = [c.strip().upper() for c in payload.target_markets if c.strip()]
    business.target_buyer_types = [t.strip() for t in payload.target_buyer_types if t.strip()]
    business.main_objective = payload.main_objective.strip() if payload.main_objective else None
    business.company_introduction = (
        payload.company_introduction.strip() if payload.company_introduction else None
    )

    await _maybe_finish(user, db)
    await db.commit()
    return OnboardingSaved(ok=True, status=await _load_status(user, db))
