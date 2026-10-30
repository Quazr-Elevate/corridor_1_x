"""Account rules: /me view model, Passport saves (split between the user
and their business), verification submission, self-service deletion."""
from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, NotFound, PayloadTooLarge, UnsupportedMediaType
from app.core.time import utcnow
from app.integrations.storage import IMAGE_TYPES, StorageError, detect, get_storage
from app.models.business import Business, BusinessStatus
from app.models.business_document import BusinessDocument
from app.models.country import Country
from app.models.kyb_document_type import KybDocumentType
from app.models.product import Product
from app.models.user import User, UserRole
from app.modules.accounts import completion
from app.modules.accounts.schemas import (
    COMPANY_OPTIONAL_FIELDS,
    PROFILE_OPTIONAL_FIELDS,
    BrandingData,
    BusinessData,
    BusinessProfileSaveIn,
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
from app.modules.verification.rules import (
    PROFILE_FIELDS,
    SUBMITTABLE_STATUSES,
    is_configured,
    reopen_review,
    requirements,
)

#: Public branding images (logo, banner) — served by ``GET /uploads/branding/<file>``.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
BRANDING_PREFIX = "branding"
BRANDING_URL_PREFIX = "/uploads/branding/"
BRANDING_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
BRANDING_SLOTS = {"logo": "logo_key", "banner": "banner_key"}


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


async def verification_state(db: AsyncSession, business: Business) -> VerificationState:
    report = await requirements(db, business)
    return VerificationState(
        status=business.verification_status.value,
        missing=[r.key for r in report.missing],
        missing_labels=[r.label for r in report.missing],
        mandatory_total=report.total,
        rejected_items=list(business.verification_rejected_items or []),
        rejected_item_labels=await _rejected_labels(db, business),
        submitted_at=business.verification_submitted_at,
        verified_at=business.verified_at,
        rejected_reason=business.verification_rejected_reason,
    )


async def _rejected_labels(db: AsyncSession, business: Business) -> list[str]:
    """Labels for the flagged keys: profile fields, ``kyb:<code>`` (the
    admin's document name), ``doc:<id>`` (the entry's custom name)."""
    items = list(business.verification_rejected_items or [])
    if not items:
        return []
    fields = {f.key: f.label for f in PROFILE_FIELDS}
    types = {
        f"kyb:{t.code}": t.name
        for t in await db.scalars(select(KybDocumentType).where(KybDocumentType.country == business.country))
    }
    entries = {
        f"doc:{d.id}": d.doc_type
        for d in await db.scalars(select(BusinessDocument).where(BusinessDocument.business_id == business.id))
    }
    return [fields.get(k) or types.get(k) or entries.get(k) or "A removed document" for k in items]


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
        verification=await verification_state(db, b),
        primary=primary_data(u),
        business=business_data(b),
        branding=branding_data(b),
        show_tour=u.tour_completed_at is None,
    )


def _branding_url(key: str | None) -> str | None:
    return f"{BRANDING_URL_PREFIX}{key.rsplit('/', 1)[-1]}" if key else None


def branding_data(b: Business) -> BrandingData:
    return BrandingData(logo_url=_branding_url(b.logo_key), banner_url=_branding_url(b.banner_key))


async def update_me(db: AsyncSession, user: User, payload: MeUpdate) -> MeResponse:
    """Personal preferences (display currency, validated against
    FX_SUPPORTED_CURRENCIES; the DB CHECK backs it)."""
    u = await reload_user(db, user.id)
    if "display_currency" in payload.model_fields_set and payload.display_currency is not None:
        u.display_currency = ensure_supported(payload.display_currency, what="Display currency")
    if "tour_completed" in payload.model_fields_set and payload.tour_completed is not None:
        u.tour_completed_at = utcnow() if payload.tour_completed else None
    await commit_or_conflict(db)
    return await me_view(db, u)


async def submit_for_verification(db: AsyncSession, user: User) -> VerificationState:
    """"Send for verification" — on the business.

    * company name, registered address, country and every mandatory KYB
      document of that country must be present (400),
    * ``verified`` businesses can't resubmit (400),
    * ``pending_verification`` is an idempotent no-op,
    * ``draft`` / ``rejected`` → ``pending_verification`` (clears the old note).
    """
    u = await reload_user(db, user.id)
    b = u.business
    report = await requirements(db, b)
    if report.missing:
        labels = ", ".join(r.label for r in report.missing)
        raise BadRequest(f"Complete your business profile before submitting. Missing: {labels}.")
    if b.verification_status == BusinessStatus.verified:
        raise BadRequest("Your business is already verified — nothing to submit.")
    if b.verification_status in SUBMITTABLE_STATUSES:
        b.verification_status = BusinessStatus.pending_verification
        b.verification_submitted_at = utcnow()
        b.verification_rejected_reason = None
        b.verification_rejected_items = None
        await db.commit()
    return await verification_state(db, b)


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
    keys: list[str] = []
    if not others:
        # Partial unique indexes ignore deleted rows, so the company name /
        # website / phone are free to register again.
        u.business.deleted_at = now
        # KYB entries go with the business (data minimisation; frees the
        # GSTIN / PAN for a fresh registration). Files are removed after commit.
        for doc in await db.scalars(select(BusinessDocument).where(BusinessDocument.business_id == u.business_id)):
            if doc.storage_key:
                keys.append(doc.storage_key)
            await db.delete(doc)
    await db.commit()
    for key in keys:
        await _delete_image(key)


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
    before = _kyb_snapshot(b)
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
        await _change_country(db, b, payload.country)  # NOT NULL column — blank leaves it unchanged
    if _kyb_snapshot(b) != before:
        reopen_review(b)
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


# ── Business profile (company name, address, country) ───────────────


async def _change_country(db: AsyncSession, business: Business, country: str) -> None:
    """KYB document types are per country, so the country can only change
    while the business has no entries of another country's types."""
    country = country.upper()
    if country == business.country:
        return
    if not await is_configured(db, country):
        raise BadRequest("Corridor One X doesn’t onboard businesses from that country yet.")
    foreign = await db.scalar(
        select(KybDocumentType.name)
        .join(BusinessDocument, BusinessDocument.document_type_id == KybDocumentType.id)
        .where(BusinessDocument.business_id == business.id, KybDocumentType.country != country)
        .limit(1)
    )
    if foreign is not None:
        raise BadRequest(
            f"Remove your {foreign} entry under Business verification before changing the country — "
            "documents differ by country."
        )
    business.country = country


async def save_profile(db: AsyncSession, user: User, payload: BusinessProfileSaveIn) -> MeResponse:
    website = payload.website_url or None
    sent = payload.model_fields_set
    await ensure_company_available(
        db, user.business_id, legal_name=payload.legal_name, website_url=website if "website_url" in sent else None
    )
    u = await reload_user(db, user.id)
    b = u.business
    before = _kyb_snapshot(b)
    b.legal_name = " ".join(payload.legal_name.split())
    await _change_country(db, b, payload.country)
    if "website_url" in sent:
        b.website_url = website
    for field in PROFILE_OPTIONAL_FIELDS:
        if field in sent:
            setattr(b, field, getattr(payload, field) or None)
    await _check_postcode(db, b)
    if _kyb_snapshot(b) != before:
        reopen_review(b)
    await commit_or_conflict(db)
    return await me_view(db, u)


async def _check_postcode(db: AsyncSession, b: Business) -> None:
    """Postcode must match the country's pattern when one is set."""
    if not b.pincode:
        return
    country = await db.get(Country, b.country)
    if country is not None and country.postal_pattern:
        if not re.fullmatch(country.postal_pattern, b.pincode.strip().upper()):
            raise BadRequest(f"That doesn’t look like a valid {country.postal_label} for {country.name}.")


def _kyb_snapshot(b: Business) -> tuple:
    """The company fields KYB verifies — a change on a verified business
    sends it back to review."""
    norm = lambda v: " ".join((v or "").split()).lower()  # noqa: E731
    return (norm(b.legal_name), norm(b.address_line), norm(b.city), (b.country or "").upper())


# ── Branding images (logo / banner) ──────────────────────────────────


async def set_branding_image(db: AsyncSession, user: User, slot: str, content: bytes) -> str:
    """Validate by magic bytes, store publicly, replace the old image."""
    column = BRANDING_SLOTS[slot]
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_IMAGE_BYTES:
        raise PayloadTooLarge("Image must be under 5 MB.")
    ftype = detect(content)
    if ftype is None or ftype not in IMAGE_TYPES:
        raise UnsupportedMediaType("Only JPG, PNG or WEBP images are supported.")
    key = f"{BRANDING_PREFIX}/{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, key, ftype.mime)
    u = await reload_user(db, user.id)
    old = getattr(u.business, column)
    setattr(u.business, column, key)
    await db.commit()
    await _delete_image(old)
    return _branding_url(key)


async def clear_branding_image(db: AsyncSession, user: User, slot: str) -> None:
    column = BRANDING_SLOTS[slot]
    u = await reload_user(db, user.id)
    old = getattr(u.business, column)
    setattr(u.business, column, None)
    await db.commit()
    await _delete_image(old)


async def _delete_image(key: str | None) -> None:
    if key:
        try:
            await get_storage().delete(key)
        except StorageError:
            pass


async def read_branding_image(filename: str) -> bytes:
    if not BRANDING_FILENAME_RE.match(filename):
        raise NotFound("Not found")
    try:
        return await get_storage().open(f"{BRANDING_PREFIX}/{filename}")
    except StorageError:
        raise NotFound("Not found") from None
