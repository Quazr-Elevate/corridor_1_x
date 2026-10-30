"""Account rules: /me view model, Passport saves (split between the user
and their business), verification submission, self-service deletion."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest
from app.core.time import utcnow
from app.models.business import Business, BusinessStatus
from app.models.business_document import BusinessDocument, DocStatus
from app.models.business_document_requirement import BusinessDocumentRequirement
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


async def verification_state(
    db: AsyncSession, owner: User | None, business: Business
) -> VerificationState:
    """Current Verified-badge state.

    ``missing`` and ``mandatory_total`` fold both the 7 mandatory profile
    fields and every mandatory country-doc requirement into one count.
    Doc entries use synthetic keys of the shape ``doc:<slug>`` so the
    frontend's existing ``MANDATORY_KEYS`` lookup transparently ignores
    them (``fieldByKey`` returns undefined) — the chip and progress bar
    only see the longer total.
    """
    missing = list(missing_mandatory_keys(owner, business))
    doc_requirements = await _active_mandatory_requirements(db, business.country)
    filled_ids = await _filled_requirement_ids(db, business, doc_requirements)
    for r in doc_requirements:
        if r.id not in filled_ids:
            missing.append(f"doc:{r.slug}")
    rejected_items = business.verification_rejected_items or []
    rejected_item_labels: dict[str, str] | None = None
    doc_slugs = [k[4:] for k in rejected_items if isinstance(k, str) and k.startswith("doc:")]
    if doc_slugs:
        label_rows = await db.scalars(
            select(BusinessDocumentRequirement)
            .where(BusinessDocumentRequirement.country_code == business.country)
            .where(BusinessDocumentRequirement.slug.in_(doc_slugs))
        )
        rejected_item_labels = {f"doc:{r.slug}": r.display_name for r in label_rows}
    return VerificationState(
        status=business.verification_status.value,
        missing=missing,
        mandatory_total=len(MANDATORY_FIELDS) + len(doc_requirements),
        submitted_at=business.verification_submitted_at,
        verified_at=business.verified_at,
        rejected_reason=business.verification_rejected_reason,
        rejected_items=business.verification_rejected_items,
        rejected_item_labels=rejected_item_labels,
    )


async def _active_mandatory_requirements(
    db: AsyncSession, country_code: str
) -> list[BusinessDocumentRequirement]:
    return list(
        await db.scalars(
            select(BusinessDocumentRequirement)
            .where(BusinessDocumentRequirement.country_code == country_code)
            .where(BusinessDocumentRequirement.is_active.is_(True))
            .where(BusinessDocumentRequirement.is_mandatory.is_(True))
            .order_by(BusinessDocumentRequirement.display_name)
        )
    )


async def _filled_requirement_ids(
    db: AsyncSession,
    business: Business,
    requirements: list[BusinessDocumentRequirement],
) -> set:
    """IDs of requirements the business has a non-rejected upload for."""
    if not requirements:
        return set()
    rows = await db.scalars(
        select(BusinessDocument.required_doc_type_id)
        .where(BusinessDocument.business_id == business.id)
        .where(BusinessDocument.required_doc_type_id.in_([r.id for r in requirements]))
        .where(BusinessDocument.status != DocStatus.rejected)
    )
    return set(rows)


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
        verification=await verification_state(db, await _owner_of(db, u), b),
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
    * every mandatory country-doc requirement must have a non-rejected
      upload tied to it (400),
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
    missing_docs = await _missing_mandatory_docs(db, b)
    if missing_docs:
        names = ", ".join(missing_docs)
        raise BadRequest(f"Upload every required document before submitting. Missing: {names}.")
    if b.verification_status == BusinessStatus.verified:
        raise BadRequest("Your business is already verified — nothing to submit.")
    if b.verification_status in SUBMITTABLE_STATUSES:
        b.verification_status = BusinessStatus.pending_verification
        b.verification_submitted_at = utcnow()
        b.verification_rejected_reason = None
        await db.commit()
    return await verification_state(db, owner, b)


async def _missing_mandatory_docs(db: AsyncSession, business: Business) -> list[str]:
    """Display names of mandatory requirements with no non-rejected upload.

    A `rejected` doc counts as missing — the user must re-upload before
    the business is submittable again.
    """
    reqs = list(
        await db.scalars(
            select(BusinessDocumentRequirement)
            .where(BusinessDocumentRequirement.country_code == business.country)
            .where(BusinessDocumentRequirement.is_active.is_(True))
            .where(BusinessDocumentRequirement.is_mandatory.is_(True))
        )
    )
    if not reqs:
        return []
    filled_ids = set(
        await db.scalars(
            select(BusinessDocument.required_doc_type_id)
            .where(BusinessDocument.business_id == business.id)
            .where(BusinessDocument.required_doc_type_id.in_([r.id for r in reqs]))
            .where(BusinessDocument.status != DocStatus.rejected)
        )
    )
    return [r.display_name for r in reqs if r.id not in filled_ids]


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
    verification status by itself — submission is an explicit user action.
    Verified businesses that edit a mandatory field are flipped back to
    ``pending_verification`` separately in ``_unverify_if_mandatory_changed``,
    called by each save function before this one."""
    await commit_or_conflict(db)
    fresh = await reload_user(db, user_id)
    return onboarding_status(fresh, fresh.business)


def _mandatory_snapshot(user: User, business: Business) -> dict[str, object]:
    """Capture the 7 mandatory-field values so a save can detect edits
    on a verified business and flip it back to ``pending_verification``."""
    return {
        "fullName": user.full_name,
        "position": user.position,
        "phone": user.phone,
        "legalName": business.legal_name,
        "industry": business.industry,
        "operatingCountries": tuple(business.operating_countries or ()),
        "tradePosition": business.trade_position,
    }


def _unverify_if_mandatory_changed(
    user: User, business: Business, before: dict[str, object]
) -> None:
    """Flip a verified business back to ``pending_verification`` whenever
    one of the 7 mandatory field values has changed since the snapshot.

    Previously-approved mandatory docs stay as-is — the admin re-reviews
    them with the updated fields in the Docs lane. The explicit
    user-triggered ``submit_for_verification`` is also skipped: the
    business is already pending once this flip runs."""
    if business.verification_status != BusinessStatus.verified:
        return
    after = _mandatory_snapshot(user, business)
    if after == before:
        return
    business.verification_status = BusinessStatus.pending_verification
    business.verified_at = None
    business.verification_submitted_at = utcnow()
    # Clear any previous reject state — this is a fresh review.
    business.verification_rejected_reason = None
    business.verification_rejected_items = None


async def save_company_info(db: AsyncSession, user: User, payload: CompanyInfoIn) -> OnboardingStatus:
    website = payload.website_url or None
    await ensure_company_available(db, user.business_id, legal_name=payload.legal_name, website_url=website)
    u = await reload_user(db, user.id)
    b = u.business
    before = _mandatory_snapshot(u, b)
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
    _unverify_if_mandatory_changed(u, b, before)
    return await _finish_save(db, u.id)


async def save_primary_contact(db: AsyncSession, user: User, payload: PrimaryContactIn) -> OnboardingStatus:
    phone = payload.phone or None
    await ensure_phone_available(db, user.id, phone)
    u = await reload_user(db, user.id)
    before = _mandatory_snapshot(u, u.business)
    u.full_name = payload.full_name
    u.phone = phone
    u.position = payload.position or None
    _unverify_if_mandatory_changed(u, u.business, before)
    return await _finish_save(db, u.id)


async def save_business_profile(db: AsyncSession, user: User, payload: BusinessProfileIn) -> OnboardingStatus:
    u = await reload_user(db, user.id)
    b = u.business
    before = _mandatory_snapshot(u, b)
    b.trade_position = payload.trade_position
    b.seller_type = payload.seller_type or None
    b.export_status = payload.export_status or None
    b.target_markets = list(payload.target_markets)
    b.target_buyer_types = list(payload.target_buyer_types)
    b.company_introduction = payload.company_introduction or None
    _unverify_if_mandatory_changed(u, b, before)
    return await _finish_save(db, u.id)
