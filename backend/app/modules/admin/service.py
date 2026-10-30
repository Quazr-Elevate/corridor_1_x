"""Admin console business rules + audit trail."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import ensure_aware, utcnow
from app.models.admin_action import AdminAction
from app.models.business import Business, BusinessStatus
from app.models.business_document import BusinessDocument, DocStatus
from app.models.business_document_requirement import BusinessDocumentRequirement
from app.models.product import Product
from app.models.user import User
from app.modules.accounts.uniqueness import (
    commit_or_conflict,
    ensure_company_available,
    ensure_phone_available,
)
from app.modules.admin.schemas import (
    DashboardStats,
    DocRequirementIn,
    DocRequirementOut,
    DocRequirementUpdate,
    PendingDocRow,
    StuckUser,
    TimelinePoint,
    UserDetail,
    UserList,
    UserPatchIn,
    UserRow,
    VerifyQueueRow,
)
from app.modules.verification.rules import (
    ADMIN_REJECTABLE_STATUSES,
    ADMIN_VERIFIABLE_STATUSES,
    MANDATORY_FIELDS,
    missing_mandatory_keys,
)
from app.modules.verification.schemas import DocOut, doc_to_out
from app.modules.accounts.service import get_owner

MAX_REASON = 500
STUCK_AFTER = timedelta(hours=24)


# ── Audit ────────────────────────────────────────────────────────────


def record_action(
    db: AsyncSession,
    *,
    admin_email: str,
    action: str,
    target_type: str,
    target_id: uuid.UUID | str,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Stage an audit row in the caller's transaction (committed with the
    change it describes)."""
    db.add(
        AdminAction(
            admin_email=admin_email,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            reason=reason,
            details=details,
            created_at=utcnow(),  # sub-second precision (SQLite's now() is per second)
        )
    )


def clean_reason(raw: str) -> str:
    reason = (raw or "").strip()
    if not reason:
        raise BadRequest("A rejection reason is required so the business knows what to fix.")
    if len(reason) > MAX_REASON:
        raise BadRequest(f"Rejection reason is too long ({MAX_REASON} chars max).")
    return reason


# ── Dashboard ────────────────────────────────────────────────────────


def _count_if(cond):
    return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)


async def dashboard_stats(db: AsyncSession) -> DashboardStats:
    since = utcnow() - STUCK_AFTER
    live_users = (
        await db.execute(
            select(func.count(User.id), _count_if(User.created_at >= since)).where(User.deleted_at.is_(None))
        )
    ).one()
    b = (
        await db.execute(
            select(
                func.count(Business.id),
                _count_if(Business.verification_status == BusinessStatus.draft),
                _count_if(Business.verification_status == BusinessStatus.pending_verification),
                _count_if(Business.verification_status == BusinessStatus.verified),
                _count_if(Business.verification_status == BusinessStatus.rejected),
                _count_if((Business.verification_status == BusinessStatus.draft) & (Business.created_at < since)),
            ).where(Business.deleted_at.is_(None))
        )
    ).one()
    other = (
        await db.execute(
            select(
                select(func.count(Product.id)).where(Product.deleted_at.is_(None)).scalar_subquery(),
                select(func.count(BusinessDocument.id))
                .where(BusinessDocument.status == DocStatus.pending)
                .scalar_subquery(),
            )
        )
    ).one()
    return DashboardStats(
        total_users=int(live_users[0]),
        recent_signups_24h=int(live_users[1]),
        total_businesses=int(b[0]),
        draft_businesses=int(b[1]),
        pending_verification_businesses=int(b[2]),
        verified_businesses=int(b[3]),
        rejected_businesses=int(b[4]),
        stuck_signups=int(b[5]),
        total_products=int(other[0] or 0),
        pending_docs=int(other[1] or 0),
    )


async def dashboard_timeline(db: AsyncSession, days: int) -> list[TimelinePoint]:
    """Daily signups for the last ``days`` days, oldest first, zero-filled."""
    start = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day = func.date(User.created_at).label("day")
    rows = await db.execute(
        select(day, func.count(User.id))
        .where(User.created_at >= start, User.deleted_at.is_(None))
        .group_by(day)
    )
    by_day = {str(d): c for d, c in rows.all()}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        out.append(TimelinePoint(date=d, count=by_day.get(d, 0)))
    return out


def _owner_join():
    """users ⋈ businesses for owners of live businesses."""
    return (
        select(User, Business)
        .join(Business, Business.id == User.business_id)
        .where(User.deleted_at.is_(None), Business.deleted_at.is_(None), User.role == "owner")
    )


async def stuck_users(db: AsyncSession, limit: int) -> list[StuckUser]:
    """Businesses still in ``draft`` 24h+ after signup (never sent for
    verification), oldest first."""
    now = utcnow()
    rows = (
        await db.execute(
            _owner_join()
            .where(Business.verification_status == BusinessStatus.draft, Business.created_at < now - STUCK_AFTER)
            .order_by(Business.created_at.asc())
            .limit(limit)
        )
    ).all()
    return [
        StuckUser(
            user_id=str(u.id),
            business_id=str(b.id),
            email=u.email,
            business_name=b.legal_name,
            created_at=b.created_at,
            hours_waiting=int((now - ensure_aware(b.created_at)).total_seconds() // 3600),
        )
        for u, b in rows
    ]


async def _docs_by_business(db: AsyncSession, business_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DocOut]]:
    out: dict[uuid.UUID, list[DocOut]] = {}
    if not business_ids:
        return out
    rows = (
        await db.execute(
            select(BusinessDocument, BusinessDocumentRequirement)
            .outerjoin(
                BusinessDocumentRequirement,
                BusinessDocumentRequirement.id == BusinessDocument.required_doc_type_id,
            )
            .where(BusinessDocument.business_id.in_(business_ids))
            .order_by(BusinessDocument.uploaded_at.asc())
        )
    ).all()
    for d, req in rows:
        out.setdefault(d.business_id, []).append(doc_to_out(d, for_admin=True, requirement=req))
    return out


async def verify_queue(db: AsyncSession) -> list[VerifyQueueRow]:
    """Businesses in ``pending_verification``, oldest submission first.

    Under the new single-review flow the admin reviews the business
    certificate and the 7 mandatory fields together in the Docs lane —
    there's no separate doc-approval gate. This query is the source for
    that queue, with each row carrying the business's docs so the
    reviewer sees everything at once.
    """
    rows = (
        await db.execute(
            _owner_join()
            .where(Business.verification_status == BusinessStatus.pending_verification)
            .order_by(Business.verification_submitted_at.asc())
        )
    ).all()
    docs = await _docs_by_business(db, [b.id for _, b in rows])
    return [
        VerifyQueueRow(
            user_id=str(u.id),
            business_id=str(b.id),
            email=u.email,
            full_name=u.full_name,
            position=u.position,
            phone=u.phone,
            business_name=b.legal_name,
            country=b.country,
            industry=b.industry,
            trade_position=b.trade_position,
            operating_countries=b.operating_countries,
            submitted_at=b.verification_submitted_at,
            created_at=b.created_at,
            missing_fields=missing_mandatory_keys(u, b),
            docs=docs.get(b.id, []),
        )
        for u, b in rows
    ]


# ── Users / businesses ───────────────────────────────────────────────


async def list_users(db: AsyncSession, *, q: str | None, status: str | None, limit: int, offset: int) -> UserList:
    stmt = (
        select(User, Business)
        .join(Business, Business.id == User.business_id)
        .where(User.deleted_at.is_(None))
    )
    if status:
        try:
            stmt = stmt.where(Business.verification_status == BusinessStatus(status))
        except ValueError:
            raise BadRequest("Unknown status") from None
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(User.email.ilike(pattern), User.full_name.ilike(pattern), Business.legal_name.ilike(pattern))
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit))).all()
    return UserList(
        total=total,
        items=[
            UserRow(
                user_id=str(u.id),
                business_id=str(b.id),
                email=u.email,
                business_name=b.legal_name,
                full_name=u.full_name,
                status=b.verification_status.value,
                email_verified=u.email_verified_at is not None,
                created_at=u.created_at,
            )
            for u, b in rows
        ],
    )


def _profile_dict(u: User) -> dict[str, Any]:
    return {"fullName": u.full_name, "phone": u.phone, "position": u.position}


def _business_dict(b: Business) -> dict[str, Any]:
    return {
        "legalName": b.legal_name,
        "entityType": b.entity_type,
        "industry": b.industry,
        "operatingCountries": b.operating_countries,
        "websiteUrl": b.website_url,
        "addressLine": b.address_line,
        "city": b.city,
        "state": b.state,
        "pincode": b.pincode,
        "country": b.country,
        "googleBusinessUrl": b.google_business_url,
        "facebookUrl": b.facebook_url,
        "tradePosition": b.trade_position,
        "sellerType": b.seller_type,
        "exportStatus": b.export_status,
        "targetMarkets": b.target_markets,
        "targetBuyerTypes": b.target_buyer_types,
        "companyIntroduction": b.company_introduction,
    }


async def load_user(db: AsyncSession, uid: uuid.UUID | None) -> User:
    """A live user with their business (fresh values — never a half-expired
    instance; lazy loads would hit MissingGreenlet under asyncio)."""
    if uid is None:
        raise NotFound("User not found")
    user = await db.scalar(select(User).where(User.id == uid).execution_options(populate_existing=True))
    if user is None or user.deleted_at is not None:
        raise NotFound("User not found")
    return user


async def _owner_for(db: AsyncSession, user: User) -> User | None:
    return user if user.role.value == "owner" else await get_owner(db, user.business_id)


async def user_detail(db: AsyncSession, uid: uuid.UUID | None) -> UserDetail:
    u = await load_user(db, uid)
    b = u.business
    product_count = (
        await db.scalar(
            select(func.count(Product.id)).where(Product.business_id == b.id, Product.deleted_at.is_(None))
        )
        or 0
    )
    docs = await db.scalars(
        select(BusinessDocument)
        .where(BusinessDocument.business_id == b.id)
        .order_by(BusinessDocument.uploaded_at.desc())
    )
    return UserDetail(
        user_id=str(u.id),
        business_id=str(b.id),
        role=u.role.value,
        email=u.email,
        email_verified_at=u.email_verified_at,
        business_name=b.legal_name,
        status=b.verification_status.value,
        created_at=u.created_at,
        updated_at=u.updated_at,
        profile=_profile_dict(u),
        business_profile=_business_dict(b),
        product_count=product_count,
        docs=[doc_to_out(d, for_admin=True) for d in docs],
        verification_submitted_at=b.verification_submitted_at,
        verified_at=b.verified_at,
        verification_rejected_reason=b.verification_rejected_reason,
        missing_mandatory_fields=missing_mandatory_keys(await _owner_for(db, u), b),
    )


def _blank_to_none(value: Any) -> Any:
    return None if value == "" else value


async def update_user(db: AsyncSession, admin_email: str, uid: uuid.UUID | None, payload: UserPatchIn) -> None:
    """Apply only the keys present in the request; same uniqueness rules
    as the self-service Passport saves. Audited as ``business.update``."""
    user = await load_user(db, uid)
    business = user.business
    changed: list[str] = []

    profile_changes = payload.profile.model_dump(exclude_unset=True) if payload.profile else {}
    business_changes = payload.business_profile.model_dump(exclude_unset=True) if payload.business_profile else {}

    # Pre-checks before any mutation (avoids autoflush surprises).
    if "phone" in profile_changes:
        await ensure_phone_available(db, user.id, profile_changes["phone"])
    if {"legal_name", "website_url"} & business_changes.keys():
        await ensure_company_available(
            db,
            business.id,
            legal_name=business_changes.get("legal_name"),
            website_url=business_changes.get("website_url"),
        )
    if "full_name" in profile_changes and not profile_changes["full_name"]:
        raise BadRequest("Full name can't be empty.")

    for key, val in profile_changes.items():
        setattr(user, key, _blank_to_none(val))
        changed.append(f"profile.{key}")
    for key, val in business_changes.items():
        if key == "country" and not val:
            continue  # NOT NULL (defaults to IN)
        setattr(business, key, _blank_to_none(val))
        changed.append(f"businessProfile.{key}")

    if changed:
        record_action(
            db,
            admin_email=admin_email,
            action="business.update",
            target_type="business",
            target_id=business.id,
            details={"fields": changed, "userId": str(user.id)},
        )
    await commit_or_conflict(db)


@dataclass(frozen=True)
class Decision:
    user_id: uuid.UUID
    business_id: uuid.UUID
    status: BusinessStatus
    email: str | None
    full_name: str | None


async def _decision(db: AsyncSession, user: User, business: Business) -> Decision:
    owner = await _owner_for(db, user)
    return Decision(
        user.id,
        business.id,
        business.verification_status,
        owner.email if owner else None,
        owner.full_name if owner else None,
    )


async def verify_user(db: AsyncSession, admin_email: str, uid: uuid.UUID | None) -> Decision:
    """Approve the user's business.

    The business cert doc(s) submitted alongside the profile are
    implicitly approved too — admins review the whole package in one
    place under the single-review flow, so a verify here cascades to
    "approved" on every pending/rejected mandatory doc.
    """
    user = await load_user(db, uid)
    b = user.business
    if b.verification_status not in ADMIN_VERIFIABLE_STATUSES:
        raise Conflict(
            "Only businesses awaiting verification can be approved "
            f"(current status: {b.verification_status.value})."
        )
    missing = missing_mandatory_keys(await _owner_for(db, user), b)
    if missing:
        raise BadRequest(f"Can't verify: mandatory fields are missing ({', '.join(missing)}).")
    now = utcnow()
    b.verification_status = BusinessStatus.verified
    b.verified_at = now
    b.verification_submitted_at = b.verification_submitted_at or now
    b.verification_rejected_reason = None
    b.verification_rejected_items = None
    await _cascade_cert_docs(db, b, admin_email, DocStatus.approved, reason=None, now=now)
    record_action(db, admin_email=admin_email, action="business.verify", target_type="business", target_id=b.id)
    decision = await _decision(db, user, b)
    await db.commit()
    return decision


async def reject_user(
    db: AsyncSession,
    admin_email: str,
    uid: uuid.UUID | None,
    reason: str,
    *,
    failed_items: list[str] | None = None,
) -> Decision:
    """Reject (or revoke) the user's business with a reason.

    ``failed_items`` is the admin's checklist of which specific items
    failed — any subset of the 7 mandatory profile keys plus
    ``doc:<slug>`` tokens. For every ``doc:*`` key picked, the business's
    pending-or-approved upload for that slug is marked rejected with the
    same reason, so the trader's Documents tab shows the file as
    "Rejected — replace it".
    """
    reason = clean_reason(reason)
    user = await load_user(db, uid)
    b = user.business
    if b.verification_status not in ADMIN_REJECTABLE_STATUSES:
        raise Conflict(
            "Only businesses awaiting verification (or verified) can be rejected "
            f"(current status: {b.verification_status.value})."
        )
    items = _validate_failed_items(failed_items or [], b)
    doc_slugs = [key.split(":", 1)[1] for key in items if key.startswith("doc:")]
    now = utcnow()
    b.verification_status = BusinessStatus.rejected
    b.verification_rejected_reason = reason
    b.verification_rejected_items = items or None
    if doc_slugs:
        await _cascade_cert_docs(
            db, b, admin_email, DocStatus.rejected, reason=reason, now=now, only_slugs=doc_slugs
        )
    record_action(
        db,
        admin_email=admin_email,
        action="business.reject",
        target_type="business",
        target_id=b.id,
        reason=reason,
        details={"failed_items": items} if items else None,
    )
    decision = await _decision(db, user, b)
    await db.commit()
    return decision


def _validate_failed_items(items: list[str], business: Business) -> list[str]:
    """Keeps only known-good keys: the 7 field keys and ``doc:<slug>`` for
    slugs currently used by one of the business's uploaded docs. Unknown
    keys are dropped silently — the admin's reason text carries the full
    context either way."""
    out: list[str] = []
    valid_fields = {f.key for f in MANDATORY_FIELDS}
    for raw in items:
        key = (raw or "").strip()
        if not key:
            continue
        if key in valid_fields:
            out.append(key)
        elif key.startswith("doc:") and len(key) > 4:
            out.append(key)
    # De-duplicate while preserving order.
    return list(dict.fromkeys(out))


async def _cascade_cert_docs(
    db: AsyncSession,
    business: Business,
    admin_email: str,
    target: DocStatus,
    *,
    reason: str | None,
    now,
    only_slugs: list[str] | None = None,
) -> None:
    """Flip the business's mandatory-cert docs to ``target``.

    - Verify flow: approve every pending/rejected cert the business has
      uploaded against a known slot (``only_slugs=None``).
    - Reject flow: reject only the cert docs whose slot slug the admin
      picked in the failed-items list (``only_slugs=[...]``).
    """
    stmt = (
        select(BusinessDocument, BusinessDocumentRequirement)
        .join(
            BusinessDocumentRequirement,
            BusinessDocumentRequirement.id == BusinessDocument.required_doc_type_id,
        )
        .where(BusinessDocument.business_id == business.id)
        .where(BusinessDocument.required_doc_type_id.is_not(None))
    )
    if only_slugs is not None:
        stmt = stmt.where(BusinessDocumentRequirement.slug.in_(only_slugs))
    for doc, _req in (await db.execute(stmt)).all():
        if doc.status == target:
            continue
        doc.status = target
        doc.reviewed_at = now
        doc.reviewed_by = admin_email
        doc.rejection_reason = reason if target == DocStatus.rejected else None


# ── Documents ────────────────────────────────────────────────────────


async def pending_docs(db: AsyncSession, *, kind: str | None = None) -> list[PendingDocRow]:
    """Pending uploads for admin review.

    ``kind=business`` returns only uploads filling a country-mandated slot
    (``required_doc_type_id`` set). ``kind=other`` returns the custom
    (free-form) uploads. ``None`` returns both.
    """
    stmt = (
        select(BusinessDocument, Business, BusinessDocumentRequirement)
        .join(Business, Business.id == BusinessDocument.business_id)
        .outerjoin(
            BusinessDocumentRequirement,
            BusinessDocumentRequirement.id == BusinessDocument.required_doc_type_id,
        )
        .where(BusinessDocument.status == DocStatus.pending, Business.deleted_at.is_(None))
    )
    if kind == "business":
        stmt = stmt.where(BusinessDocument.required_doc_type_id.is_not(None))
    elif kind == "other":
        stmt = stmt.where(BusinessDocument.required_doc_type_id.is_(None))
    elif kind is not None:
        raise BadRequest("kind must be 'business' or 'other'.")
    rows = (await db.execute(stmt.order_by(BusinessDocument.uploaded_at.asc()))).all()
    out = []
    for d, b, req in rows:
        owner = await get_owner(db, b.id)
        out.append(
            PendingDocRow(
                doc=doc_to_out(d, for_admin=True, requirement=req),
                user_id=str(owner.id) if owner else None,
                business_id=str(b.id),
                user_email=owner.email if owner else None,
                user_business_name=b.legal_name,
                user_full_name=owner.full_name if owner else None,
                user_country=b.country,
            )
        )
    return out


@dataclass(frozen=True)
class DocDecision:
    doc_id: uuid.UUID
    status: DocStatus
    cert_type: str
    owner_email: str | None
    owner_name: str | None


async def review_doc(
    db: AsyncSession,
    admin_email: str,
    doc_id: uuid.UUID | None,
    target: DocStatus,
    *,
    reason: str | None = None,
) -> DocDecision:
    if target == DocStatus.rejected:
        reason = clean_reason(reason or "")
    doc = await db.get(BusinessDocument, doc_id) if doc_id else None
    if doc is None:
        raise NotFound("Document not found")
    doc.status = target
    doc.reviewed_at = utcnow()
    doc.reviewed_by = admin_email
    doc.rejection_reason = reason if target == DocStatus.rejected else None
    record_action(
        db,
        admin_email=admin_email,
        action=f"doc.{'reject' if target == DocStatus.rejected else 'approve'}",
        target_type="document",
        target_id=doc.id,
        reason=reason if target == DocStatus.rejected else None,
        details={"businessId": str(doc.business_id), "docType": doc.doc_type},
    )
    owner = await get_owner(db, doc.business_id)
    result = DocDecision(
        doc_id=doc.id,
        status=target,
        cert_type=doc.doc_type,
        owner_email=owner.email if owner else None,
        owner_name=owner.full_name if owner else None,
    )
    await db.commit()
    return result


# ── Country document requirements (admin CRUD) ──────────────────────


def _req_to_out(r: BusinessDocumentRequirement) -> DocRequirementOut:
    return DocRequirementOut(
        id=str(r.id),
        country_code=r.country_code,
        slug=r.slug,
        display_name=r.display_name,
        description=r.description,
        help_url=r.help_url,
        is_mandatory=r.is_mandatory,
        is_active=r.is_active,
        created_by=r.created_by,
        updated_by=r.updated_by,
        created_at=ensure_aware(r.created_at),
        updated_at=ensure_aware(r.updated_at),
    )


async def list_doc_requirements(
    db: AsyncSession, *, country: str | None, include_inactive: bool
) -> list[DocRequirementOut]:
    """Return the catalog, newest first within (country, is_active) grouping."""
    stmt = select(BusinessDocumentRequirement)
    if country:
        stmt = stmt.where(BusinessDocumentRequirement.country_code == country.upper())
    if not include_inactive:
        stmt = stmt.where(BusinessDocumentRequirement.is_active.is_(True))
    stmt = stmt.order_by(
        BusinessDocumentRequirement.country_code,
        BusinessDocumentRequirement.is_active.desc(),
        BusinessDocumentRequirement.display_name,
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_req_to_out(r) for r in rows]


async def create_doc_requirement(
    db: AsyncSession, admin_email: str, payload: DocRequirementIn
) -> DocRequirementOut:
    """Create a new catalog row. Conflicts if an active row exists for the
    same (country, slug) — the admin should either reuse it or deactivate
    the old one first."""
    row = BusinessDocumentRequirement(
        country_code=payload.country_code,
        slug=payload.slug,
        display_name=payload.display_name,
        description=payload.description,
        help_url=payload.help_url,
        is_mandatory=payload.is_mandatory,
        is_active=True,
        created_by=admin_email,
        updated_by=admin_email,
    )
    db.add(row)
    record_action(
        db,
        admin_email=admin_email,
        action="doc_requirement.create",
        target_type="doc_requirement",
        target_id=row.id,
        details={
            "country_code": row.country_code,
            "slug": row.slug,
            "display_name": row.display_name,
            "is_mandatory": row.is_mandatory,
        },
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise Conflict(
            f"A requirement for {payload.country_code}/{payload.slug} already exists."
        ) from None
    await db.refresh(row)
    return _req_to_out(row)


async def update_doc_requirement(
    db: AsyncSession, admin_email: str, req_id: uuid.UUID, payload: DocRequirementUpdate
) -> DocRequirementOut:
    """PATCH-style merge. ``country_code`` / ``slug`` stay immutable."""
    row = await db.get(BusinessDocumentRequirement, req_id)
    if row is None:
        raise NotFound("Requirement not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _req_to_out(row)
    before = {k: getattr(row, k) for k in data}
    for k, v in data.items():
        setattr(row, k, v)
    row.updated_by = admin_email
    row.updated_at = utcnow()
    record_action(
        db,
        admin_email=admin_email,
        action="doc_requirement.update",
        target_type="doc_requirement",
        target_id=row.id,
        details={"before": _jsonable(before), "after": _jsonable(data)},
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise Conflict(
            "This change collides with another active row for the same country+slug."
        ) from None
    await db.refresh(row)
    return _req_to_out(row)


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    """Make the audit-log details column JSON-safe for enum / UUID values."""
    return {k: (v.value if hasattr(v, "value") else v) for k, v in d.items()}
