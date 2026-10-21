"""Account rules: /me view model, Passport saves (split between the user
and their business), verification submission, self-service deletion."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest
from app.core.time import utcnow
from app.models.business import Business, BusinessStatus
from app.models.product import Product
from app.models.user import User, UserRole
from app.modules.accounts import completion
from app.modules.accounts.schemas import (
    COMPANY_OPTIONAL_FIELDS,
    BusinessData,
    BusinessProfileIn,
    CompanyInfoIn,
    MeResponse,
    MeUpdate,
    OnboardingStatus,
    PrimaryContactIn,
    PrimaryData,
    VerificationState,
)
from app.modules.accounts.uniqueness import (
    commit_or_conflict,
    ensure_company_available,
    ensure_phone_available,
)
from app.modules.fx.service import ensure_supported
from app.modules.verification.rules import MANDATORY_FIELDS, SUBMITTABLE_STATUSES, missing_mandatory_keys


async def reload_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    """User + business (joined) with fresh attribute values."""
    return (
        await db.execute(select(User).where(User.id == user_id).execution_options(populate_existing=True))
    ).scalar_one()


async def get_owner(db: AsyncSession, business_id: uuid.UUID) -> User | None:
    """The business's owner (oldest active owner) — the person behind the
    mandatory fields and the revealed contact."""
    return await db.scalar(
        select(User)
        .where(User.business_id == business_id, User.role == UserRole.owner, User.deleted_at.is_(None))
        .order_by(User.created_at.asc())
        .limit(1)
    )


async def _owner_of(db: AsyncSession, user: User) -> User | None:
    return user if user.role == UserRole.owner else await get_owner(db, user.business_id)


def verification_state(owner: User | None, business: Business) -> VerificationState:
    return VerificationState(
        status=business.verification_status.value,
        missing=missing_mandatory_keys(owner, business),
        mandatory_total=len(MANDATORY_FIELDS),
        submitted_at=business.verification_submitted_at,
        verified_at=business.verified_at,
        rejected_reason=business.verification_rejected_reason,
    )


def primary_data(u: User) -> PrimaryData:
    return PrimaryData(full_name=u.full_name, phone=u.phone, position=u.position)


def business_data(b: Business) -> BusinessData:
    return BusinessData(
        legal_name=b.legal_name,
        entity_type=b.entity_type,
        industry=b.industry,
        operating_countries=b.operating_countries,
        website_url=b.website_url,
        address_line=b.address_line,
        city=b.city,
        state=b.state,
        pincode=b.pincode,
        country=b.country,
        google_business_url=b.google_business_url,
        facebook_url=b.facebook_url,
        trade_position=b.trade_position,
        seller_type=b.seller_type,
        export_status=b.export_status,
        target_markets=b.target_markets,
        target_buyer_types=b.target_buyer_types,
        company_introduction=b.company_introduction,
    )


async def me_view(db: AsyncSession, user: User) -> MeResponse:
    u = await reload_user(db, user.id)
    b = u.business
    product_count = (
        await db.scalar(
            select(func.count(Product.id)).where(Product.business_id == b.id, Product.deleted_at.is_(None))
        )
        or 0
    )
    return MeResponse(
        user_id=str(u.id),
        business_id=str(b.id),
        role=u.role.value,
        email=u.email,
        email_verified_at=u.email_verified_at,
        business_name=b.legal_name,
        display_currency=u.display_currency,
        user_type="seller" if product_count > 0 else "buyer",
        status=b.verification_status.value,
        verification=verification_state(await _owner_of(db, u), b),
        primary=primary_data(u),
        business=business_data(b),
    )


async def update_me(db: AsyncSession, user: User, payload: MeUpdate) -> MeResponse:
    """Personal preferences (display currency, validated against
    FX_SUPPORTED_CURRENCIES; the DB CHECK backs it)."""
    u = await reload_user(db, user.id)
    if "display_currency" in payload.model_fields_set and payload.display_currency is not None:
        u.display_currency = ensure_supported(payload.display_currency, what="Display currency")
    await commit_or_conflict(db)
    return await me_view(db, u)


async def submit_for_verification(db: AsyncSession, user: User) -> VerificationState:
    """"Send for verification" — on the business.

    * all seven mandatory fields must be filled (400),
    * ``verified`` businesses can't resubmit (400),
    * ``pending_verification`` is an idempotent no-op,
    * ``draft`` / ``rejected`` → ``pending_verification`` (clears the old note).
    """
    u = await reload_user(db, user.id)
    b = u.business
    owner = await _owner_of(db, u)
    missing = missing_mandatory_keys(owner, b)
    if missing:
        raise BadRequest(f"Fill every mandatory field before submitting. Missing: {', '.join(missing)}.")
    if b.verification_status == BusinessStatus.verified:
        raise BadRequest("Your business is already verified — nothing to submit.")
    if b.verification_status in SUBMITTABLE_STATUSES:
        b.verification_status = BusinessStatus.pending_verification
        b.verification_submitted_at = utcnow()
        b.verification_rejected_reason = None
        await db.commit()
    return verification_state(owner, b)


async def delete_account(db: AsyncSession, user: User) -> None:
    """Soft-delete (DPDP right-to-erasure): anonymise the login handle and
    personal fields, release unique keys, revoke all sessions. When no
    other active user remains, the business is soft-deleted too (its
    listings leave the market)."""
    u = await reload_user(db, user.id)
    now = utcnow()
    u.deleted_at = now
    u.email = f"deleted-{u.id}@deleted.local"
    u.full_name = "Deleted user"
    u.phone = None
    u.position = None
    u.session_version = (u.session_version or 0) + 1
    others = await db.scalar(
        select(func.count(User.id)).where(
            User.business_id == u.business_id, User.id != u.id, User.deleted_at.is_(None)
        )
    )
    if not others:
        # Partial unique indexes ignore deleted rows, so the company name /
        # website / phone are free to register again.
        u.business.deleted_at = now
    await db.commit()


# ── Passport saves ───────────────────────────────────────────────────


def onboarding_status(user: User | None, business: Business | None) -> OnboardingStatus:
    return OnboardingStatus(
        company_info_done=completion.company_info_done(business),
        primary_contact_done=completion.primary_contact_done(user),
        business_profile_done=completion.business_profile_done(business),
    )


async def get_onboarding_status(db: AsyncSession, user: User) -> OnboardingStatus:
    u = await reload_user(db, user.id)
    return onboarding_status(u, u.business)


async def _finish_save(db: AsyncSession, user_id: uuid.UUID) -> OnboardingStatus:
    """Commit (unique-index races → 409). Saving never changes the
    verification status — submission is an explicit user action."""
    await commit_or_conflict(db)
    fresh = await reload_user(db, user_id)
    return onboarding_status(fresh, fresh.business)


async def save_company_info(db: AsyncSession, user: User, payload: CompanyInfoIn) -> OnboardingStatus:
    website = payload.website_url or None
    await ensure_company_available(db, user.business_id, legal_name=payload.legal_name, website_url=website)
    u = await reload_user(db, user.id)
    b = u.business
    b.legal_name = payload.legal_name
    b.industry = payload.industry
    b.operating_countries = list(payload.operating_countries)
    b.website_url = website
    if "entity_type" in payload.model_fields_set:
        b.entity_type = payload.entity_type
    for field in COMPANY_OPTIONAL_FIELDS:
        if field in payload.model_fields_set:
            setattr(b, field, getattr(payload, field) or None)
    if "country" in payload.model_fields_set and payload.country:
        b.country = payload.country  # NOT NULL column — blank leaves it unchanged
    return await _finish_save(db, u.id)


async def save_primary_contact(db: AsyncSession, user: User, payload: PrimaryContactIn) -> OnboardingStatus:
    phone = payload.phone or None
    await ensure_phone_available(db, user.id, phone)
    u = await reload_user(db, user.id)
    u.full_name = payload.full_name
    u.phone = phone
    u.position = payload.position or None
    return await _finish_save(db, u.id)


async def save_business_profile(db: AsyncSession, user: User, payload: BusinessProfileIn) -> OnboardingStatus:
    u = await reload_user(db, user.id)
    b = u.business
    b.trade_position = payload.trade_position
    b.seller_type = payload.seller_type or None
    b.export_status = payload.export_status or None
    b.target_markets = list(payload.target_markets)
    b.target_buyer_types = list(payload.target_buyer_types)
    b.company_introduction = payload.company_introduction or None
    return await _finish_save(db, u.id)
