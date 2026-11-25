"""Admin console business rules + audit trail."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import ensure_aware, utcnow
from app.models.admin_action import AdminAction
from app.models.admin_user import AdminUser
from app.models.business import Business, BusinessStatus
from app.models.business_identity import BusinessIdentity
from app.models.business_document import BusinessDocument, DocStatus
from app.models.country import Country
from app.models.kyb_document_type import KybDocumentType
from app.models.product import Product
from app.models.user_identity import UserIdentity
from app.models.user import User
from app.modules.accounts.uniqueness import commit_or_conflict, ensure_phone_available
from app.modules.masking import service as masking
from app.modules.admin.schemas import (
    AccountSecurityOut,
    SessionOut,
    DashboardStats,
    PendingDocRow,
    ReviewEvent,
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
    PROFILE_FIELDS,
    document_rule_problems,
    reopen_review,
    requirements,
)
from app.modules.verification.schemas import DocOut, doc_to_out
from app.modules.accounts.service import change_country, get_owner, item_labels, kyb_snapshot, owner_contact
from app.modules.auth.lockout import lock_state
from app.modules.auth.sessions import live_sessions, user_policy

MAX_REASON = 500
#: A reason the business can act on; "x" is not one.
MIN_REASON = 10
STUCK_AFTER = timedelta(hours=24)


# ── Audit ────────────────────────────────────────────────────────────


class Actor(Protocol):
    """Who acted — an ``AdminPrincipal`` (``deps.py``)."""

    id: uuid.UUID
    email: str


def record_action(
    db: AsyncSession,
    *,
    admin: Actor,
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
            admin_email=admin.email,
            admin_user_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            reason=reason,
            details=details,
            created_at=utcnow(),  # sub-second precision (SQLite's now() is per second)
        )
    )


async def missing_keys(db: AsyncSession, business: Business) -> list[str]:
    return [r.key for r in (await requirements(db, business)).missing]


def clean_reason(raw: str) -> str:
    reason = (raw or "").strip()
    if not reason:
        raise BadRequest("A rejection reason is required so the business knows what to fix.")
    if len(reason) < MIN_REASON:
        raise BadRequest(
            f"Write at least {MIN_REASON} characters so the business knows what to fix, e.g. "
            "“The address doesn't match the GST certificate.”"
        )
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


async def stuck_users(db: AsyncSession, admin: Actor, limit: int) -> list[StuckUser]:
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
    names = await masking.names_for_staff(db, admin, [b.id for _, b in rows], purpose="stuck_users")
    people = await masking.people_for_staff(db, admin, [u.id for u, _ in rows], purpose="stuck_users")
    return [
        StuckUser(
            user_id=str(u.id),
            business_id=str(b.id),
            email=people[u.id].email,
            business_name=names.get(b.id),
            created_at=b.created_at,
            hours_waiting=int((now - ensure_aware(b.created_at)).total_seconds() // 3600),
        )
        for u, b in rows
    ]


async def _docs_by_business(db: AsyncSession, business_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DocOut]]:
    out: dict[uuid.UUID, list[DocOut]] = {}
    if not business_ids:
        return out
    rows = await db.scalars(
        select(BusinessDocument)
        .where(BusinessDocument.business_id.in_(business_ids))
        .order_by(BusinessDocument.uploaded_at.asc())
    )
    for d in rows:
        out.setdefault(d.business_id, []).append(doc_to_out(d, for_admin=True))
    return out


async def verify_queue(db: AsyncSession, admin: Actor) -> list[VerifyQueueRow]:
    """The single KYB review queue, oldest first:

    * businesses sent for verification (``pending_verification``), and
    * verified businesses that added or changed documents still pending
      (reviewed per document; the business stays verified).
    """
    pending_doc = (
        select(BusinessDocument.business_id)
        .where(BusinessDocument.status == DocStatus.pending)
        .distinct()
    )
    rows = (
        await db.execute(
            _owner_join().where(
                or_(
                    Business.verification_status == BusinessStatus.pending_verification,
                    and_(Business.verification_status == BusinessStatus.verified, Business.id.in_(pending_doc)),
                )
            )
        )
    ).all()
    docs = await _docs_by_business(db, [b.id for _, b in rows])
    missing = {b.id: await missing_keys(db, b) for _, b in rows}
    names = await masking.names_for_staff(db, admin, [b.id for _, b in rows], purpose="verify_queue")
    people = await masking.people_for_staff(db, admin, [u.id for u, _ in rows], purpose="verify_queue")
    twins = await masking.same_name_codes(db, [b.id for _, b in rows])

    def since(b: Business):
        if b.verification_status == BusinessStatus.pending_verification:
            return b.verification_submitted_at or b.created_at
        pend = [d.uploaded_at for d in docs.get(b.id, []) if d.status == DocStatus.pending.value]
        return min(pend) if pend else b.created_at

    out = [
        VerifyQueueRow(
            user_id=str(u.id),
            business_id=str(b.id),
            email=people[u.id].email,
            full_name=people[u.id].full_name,
            business_name=names.get(b.id),
            company_code=b.company_code,
            same_name_as=twins.get(b.id, []),
            country=b.country,
            industry=b.industry,
            trade_position=b.trade_position,
            operating_countries=b.operating_countries,
            submitted_at=since(b),
            created_at=b.created_at,
            missing_fields=missing.get(b.id, []),
            docs=docs.get(b.id, []),
            review_kind="submitted" if b.verification_status == BusinessStatus.pending_verification else "documents",
            status=b.verification_status.value,
        )
        for u, b in rows
    ]
    return sorted(out, key=lambda r: r.submitted_at or r.created_at)


# ── Users / businesses ───────────────────────────────────────────────


async def list_users(
    db: AsyncSession, admin: Actor, *, q: str | None, status: str | None, limit: int, offset: int
) -> UserList:
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
            or_(
                masking.person_matches(pattern),
                Business.company_code.ilike(pattern),
                masking.name_matches(pattern),
            )
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit))).all()
    names = await masking.names_for_staff(db, admin, [b.id for _, b in rows], purpose="directory")
    people = await masking.people_for_staff(db, admin, [u.id for u, _ in rows], purpose="directory")
    last = await last_business_reviews(db, [b for _, b in rows])
    return UserList(
        total=total,
        items=[
            UserRow(
                user_id=str(u.id),
                business_id=str(b.id),
                email=people[u.id].email,
                business_name=names.get(b.id),
                company_code=b.company_code,
                full_name=people[u.id].full_name,
                status=b.verification_status.value,
                email_verified=u.email_verified_at is not None,
                created_at=u.created_at,
                last_review=last.get(b.id),
            )
            for u, b in rows
        ],
    )


def _profile_dict(u: User, person: UserIdentity) -> dict[str, Any]:
    return {"fullName": person.full_name, "phone": person.phone, "position": u.position}


def _business_dict(b: Business, identity: BusinessIdentity) -> dict[str, Any]:
    return {
        "legalName": identity.legal_name,
        "entityType": b.entity_type,
        "industry": b.industry,
        "operatingCountries": b.operating_countries,
        "websiteUrl": identity.website_url,
        "addressLine": identity.address_line,
        "state": b.state,
        "country": b.country,
        "googleBusinessUrl": identity.google_business_url,
        "facebookUrl": identity.facebook_url,
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


async def _account_security(db: AsyncSession, u: User) -> AccountSecurityOut:
    now = utcnow()
    live = await live_sessions(db, user_policy(), u.id)
    active = live[0] if live else None
    state = lock_state(u, now)
    return AccountSecurityOut(
        lock_state=state,
        locked_until=u.locked_until if state == "temporary" else None,
        failed_login_count=u.failed_login_count,
        active_session=SessionOut.model_validate(active, from_attributes=True) if active else None,
        active_session_count=len(live),
        last_login_at=u.last_login_at,
    )


# ── Review history (who decided what, from the audit trail) ──────────

_BUSINESS_DECISIONS = {"business.verify": "business_approved", "business.reject": "business_rejected"}
_DOC_DECISIONS = {"doc.approve": "document_approved", "doc.reject": "document_rejected"}


async def _reviewer_names(db: AsyncSession, rows: list[AdminAction]) -> dict[uuid.UUID, str]:
    ids = {r.admin_user_id for r in rows if r.admin_user_id}
    if not ids:
        return {}
    return dict((await db.execute(select(AdminUser.id, AdminUser.full_name).where(AdminUser.id.in_(ids)))).all())


async def _events(db: AsyncSession, b: Business, rows: list[AdminAction]) -> list[ReviewEvent]:
    names = await _reviewer_names(db, rows)
    out: list[ReviewEvent] = []
    for r in rows:
        details = r.details or {}
        kind = _BUSINESS_DECISIONS.get(r.action) or _DOC_DECISIONS[r.action]
        out.append(ReviewEvent(
            at=r.created_at,
            kind=kind,
            # Rows from before named admin accounts (0024) carry only the email.
            reviewer_name=names.get(r.admin_user_id) if r.admin_user_id else None,
            reviewer_email=r.admin_email,
            reason=r.reason,
            items=await item_labels(db, b, list(details.get("failed_items") or [])),
            document=details.get("docType") if r.action in _DOC_DECISIONS else None,
            documents_approved=details.get("documents_approved"),
        ))
    return out


async def review_history(db: AsyncSession, b: Business) -> list[ReviewEvent]:
    """Every approve / reject of the business and of its documents, newest
    first. Document decisions are matched by the business id they carry, so
    a decision on a document deleted since still shows."""
    rows = list(await db.scalars(
        select(AdminAction)
        .where(or_(
            and_(
                AdminAction.target_type == "business",
                AdminAction.target_id == str(b.id),
                AdminAction.action.in_(_BUSINESS_DECISIONS),
            ),
            and_(
                AdminAction.target_type == "document",
                AdminAction.action.in_(_DOC_DECISIONS),
                AdminAction.details["businessId"].as_string() == str(b.id),
            ),
        ))
        .order_by(AdminAction.created_at.desc())
    ))
    return await _events(db, b, rows)


async def last_business_reviews(db: AsyncSession, businesses: list[Business]) -> dict[uuid.UUID, ReviewEvent]:
    """The latest approve / reject of each business (directory rows)."""
    if not businesses:
        return {}
    by_id = {str(b.id): b for b in businesses}
    rows = list(await db.scalars(
        select(AdminAction)
        .where(
            AdminAction.target_type == "business",
            AdminAction.target_id.in_(by_id),
            AdminAction.action.in_(_BUSINESS_DECISIONS),
        )
        .order_by(AdminAction.created_at.desc())
    ))
    latest: dict[str, AdminAction] = {}
    for r in rows:
        latest.setdefault(r.target_id, r)
    out: dict[uuid.UUID, ReviewEvent] = {}
    for target, r in latest.items():
        b = by_id[target]
        out[b.id] = (await _events(db, b, [r]))[0]
    return out


async def user_detail(
    db: AsyncSession, admin: Actor, uid: uuid.UUID | None, *, reason: str | None = None
) -> UserDetail:
    """One account with its company identity. Stages ``identity.unmasked``
    with the admin's reason (none after an edit, which is its own audited
    action); the router commits."""
    u = await load_user(db, uid)
    b = u.business
    purpose = "account_detail" if reason else "account_edit"
    identity = await masking.unmask_for_staff(db, admin, b.id, purpose=purpose, reason=reason, user_id=u.id)
    person = await masking.person_for_staff(db, u.id)
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
        same_name_as=(await masking.same_name_codes(db, [b.id]))[b.id],
        related_to=await related_codes(db, b),
        unopened_doc_ids=[str(d.id) for d in await unopened_required_docs(db, admin.id, b.id)],
        role=u.role.value,
        email=person.email,
        email_verified_at=u.email_verified_at,
        business_name=identity.legal_name,
        company_code=b.company_code,
        status=b.verification_status.value,
        created_at=u.created_at,
        updated_at=u.updated_at,
        profile=_profile_dict(u, person),
        business_profile=_business_dict(b, identity),
        product_count=product_count,
        docs=[doc_to_out(d, for_admin=True) for d in docs],
        verification_submitted_at=b.verification_submitted_at,
        verified_at=b.verified_at,
        verification_rejected_reason=b.verification_rejected_reason,
        verification_rejected_items=list(b.verification_rejected_items or []),
        missing_mandatory_fields=await missing_keys(db, b),
        security=await _account_security(db, u),
        review_history=await review_history(db, b),
    )


def _blank_to_none(value: Any) -> Any:
    return None if value == "" else value


async def update_user(db: AsyncSession, admin: Actor, uid: uuid.UUID | None, payload: UserPatchIn) -> None:
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
        await masking.ensure_company_available(
            db,
            business.id,
            website_url=business_changes.get("website_url"),
        )
    if "full_name" in profile_changes and not profile_changes["full_name"]:
        raise BadRequest("Full name can't be empty.")
    # The fields the Verified badge rests on can be corrected, not blanked.
    for field in PROFILE_FIELDS:
        if field.column in business_changes and not business_changes[field.column]:
            raise BadRequest(f"{field.label} is required. Enter the corrected value instead of clearing it.")

    person = await masking.own_person(db, user.id) if profile_changes else None
    for key, val in profile_changes.items():
        masking.set_person_field(user, person, key, _blank_to_none(val))
        changed.append(f"profile.{key}")
    identity = await masking.own_identity(db, business.id)
    before = kyb_snapshot(business, identity)
    for key, val in business_changes.items():
        if key == "country":
            await change_country(db, business, val, by_staff=True)
        else:
            masking.set_company_field(business, identity, key, _blank_to_none(val))
        changed.append(f"businessProfile.{key}")
    # As when the business edits these itself: a verified business goes back
    # to review, and its listings leave the market until it is approved.
    reopened = kyb_snapshot(business, identity) != before and reopen_review(business)

    if changed:
        record_action(
            db,
            admin=admin,
            action="business.update",
            target_type="business",
            target_id=business.id,
            details={"fields": changed, "userId": str(user.id), **({"reopenedReview": True} if reopened else {})},
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
    contact = await masking.contact_of(db, owner.id) if owner else None
    return Decision(
        user.id,
        business.id,
        business.verification_status,
        contact.email if contact else None,
        contact.full_name if contact else None,
    )


async def related_codes(db: AsyncSession, business: Business) -> list[str]:
    """Other live businesses that share this one's group document (India: the
    PAN behind several GSTINs, A-052), as company codes, "unverified" when
    they have none yet. Compared by keyed hash; no number is read."""
    country = await db.get(Country, business.country)
    if country is None or country.group_document_type_id is None:
        return []
    mine = await db.scalar(
        select(BusinessDocument.value_hash).where(
            BusinessDocument.business_id == business.id,
            BusinessDocument.document_type_id == country.group_document_type_id,
            BusinessDocument.value_hash.is_not(None),
            BusinessDocument.status != DocStatus.rejected,
        )
    )
    if mine is None:
        return []
    codes = await db.scalars(
        select(Business.company_code)
        .join(BusinessDocument, BusinessDocument.business_id == Business.id)
        .where(
            BusinessDocument.document_type_id == country.group_document_type_id,
            BusinessDocument.value_hash == mine,
            BusinessDocument.status != DocStatus.rejected,
            Business.id != business.id,
            Business.deleted_at.is_(None),
        )
    )
    return sorted(code or "unverified" for code in codes)


async def unopened_required_docs(db: AsyncSession, admin_id: uuid.UUID, business_id: uuid.UUID) -> list[BusinessDocument]:
    """The pending required documents this admin hasn't opened since they
    were uploaded: the file, or the full number when there is no file
    (A-054). Opening is read from the audit log the reveal routes write."""
    docs = list(await db.scalars(
        select(BusinessDocument)
        .join(KybDocumentType, KybDocumentType.id == BusinessDocument.document_type_id)
        .where(
            BusinessDocument.business_id == business_id,
            BusinessDocument.status == DocStatus.pending,
            KybDocumentType.is_mandatory.is_(True),
        )
    ))
    if not docs:
        return []
    opened = (await db.execute(
        select(AdminAction.target_id, AdminAction.action, func.max(AdminAction.created_at))
        .where(
            AdminAction.admin_user_id == admin_id,
            AdminAction.action.in_(("kyb.file_viewed", "kyb.value_viewed")),
            AdminAction.target_id.in_([str(d.id) for d in docs]),
        )
        .group_by(AdminAction.target_id, AdminAction.action)
    )).all()
    seen = {(target, action): ensure_aware(when) for target, action, when in opened}

    def was_opened(d: BusinessDocument) -> bool:
        action = "kyb.file_viewed" if d.storage_key else "kyb.value_viewed"
        when = seen.get((str(d.id), action))
        return when is not None and when >= ensure_aware(d.uploaded_at)

    return [d for d in docs if not was_opened(d)]


async def verify_user(db: AsyncSession, admin: Actor, uid: uuid.UUID | None) -> Decision:
    """Approve the user's business, once this admin has opened every
    required document it rests on (A-054)."""
    user = await load_user(db, uid)
    b = user.business
    if b.verification_status not in ADMIN_VERIFIABLE_STATUSES:
        raise Conflict(
            "Only businesses awaiting verification can be approved "
            f"(current status: {b.verification_status.value})."
        )
    report = await requirements(db, b)
    if report.missing:
        labels = ", ".join(r.label for r in report.missing)
        raise BadRequest(f"Can't verify: the business profile is incomplete ({labels}).")
    mismatched = await document_rule_problems(db, b)
    if mismatched:
        raise BadRequest("Can't verify: " + " ".join(mismatched))
    unopened = await unopened_required_docs(db, admin.id, b.id)
    if unopened:
        names = ", ".join(sorted({d.doc_type for d in unopened}))
        raise Conflict(f"Open each required document before approving. Not opened yet: {names}.")
    now = utcnow()
    b.verification_status = BusinessStatus.verified
    b.verified_at = now
    await masking.assign_code(db, b)
    b.verification_submitted_at = b.verification_submitted_at or now
    b.verification_rejected_reason = None
    b.verification_rejected_items = None
    # One review: approving the business approves the documents verification
    # rests on — its pending *required* entries. Optional and "Other" uploads
    # keep their own per-document decision (nothing unseen gets approved).
    approved = await _set_doc_status(db, b.id, admin, DocStatus.approved, now=now, required_only=True)
    record_action(
        db, admin=admin, action="business.verify", target_type="business", target_id=b.id,
        details={"documents_approved": len(approved)} if approved else None,
    )
    decision = await _decision(db, user, b)
    await db.commit()
    return decision


async def reject_user(
    db: AsyncSession,
    admin: Actor,
    uid: uuid.UUID | None,
    reason: str,
    failed_items: list[str] | None = None,
) -> Decision:
    """Reject (or revoke) the user's business with a reason and the items
    that failed. Flagged KYB entries are rejected with the same reason."""
    reason = clean_reason(reason)
    user = await load_user(db, uid)
    b = user.business
    if b.verification_status not in ADMIN_REJECTABLE_STATUSES:
        raise Conflict(
            "Only businesses awaiting verification (or verified) can be rejected "
            f"(current status: {b.verification_status.value})."
        )
    entries = list(await db.scalars(select(BusinessDocument).where(BusinessDocument.business_id == b.id)))
    items = _valid_failed_items(failed_items or [], entries)
    b.verification_status = BusinessStatus.rejected
    b.verification_rejected_reason = reason
    b.verification_rejected_items = items or None
    flagged = {e.id for e in entries if _entry_key(e) in items}
    now = utcnow()
    for e in entries:
        if e.id in flagged:
            e.status = DocStatus.rejected
            e.rejection_reason = reason
            e.reviewed_at = now
            e.reviewed_by = admin.email
    record_action(
        db, admin=admin, action="business.reject", target_type="business", target_id=b.id, reason=reason,
        details={"failed_items": items} if items else None,
    )
    decision = await _decision(db, user, b)
    await db.commit()
    return decision


def _entry_key(e: BusinessDocument) -> str:
    """Stable key of a KYB entry in ``failed_items``."""
    return f"kyb:{e.document_type.code}" if e.document_type is not None else f"doc:{e.id}"


def _valid_failed_items(items: list[str], entries: list[BusinessDocument]) -> list[str]:
    """Keep known keys only (profile fields + this business's entries + its
    still-missing required documents), in a stable order, de-duplicated."""
    allowed = [f.key for f in PROFILE_FIELDS] + [_entry_key(e) for e in entries]
    unknown = [i for i in items if i not in allowed and not i.startswith("kyb:")]
    if unknown:
        raise BadRequest(f"Unknown item(s) to fix: {', '.join(unknown[:5])}.")
    seen: list[str] = []
    for i in items:
        if i not in seen:
            seen.append(i)
    return seen


async def _set_doc_status(
    db: AsyncSession, business_id: uuid.UUID, admin: Actor, status: DocStatus, *, now, required_only: bool = False
) -> list[BusinessDocument]:
    stmt = select(BusinessDocument).where(
        BusinessDocument.business_id == business_id, BusinessDocument.status == DocStatus.pending
    )
    if required_only:
        stmt = stmt.join(KybDocumentType, KybDocumentType.id == BusinessDocument.document_type_id).where(
            KybDocumentType.is_mandatory.is_(True)
        )
    rows = list(await db.scalars(stmt))
    for d in rows:
        d.status = status
        d.rejection_reason = None
        d.reviewed_at = now
        d.reviewed_by = admin.email
    return rows


# ── Documents ────────────────────────────────────────────────────────


async def pending_docs(db: AsyncSession, admin: Actor) -> list[PendingDocRow]:
    rows = (
        await db.execute(
            select(BusinessDocument, Business)
            .join(Business, Business.id == BusinessDocument.business_id)
            .where(BusinessDocument.status == DocStatus.pending, Business.deleted_at.is_(None))
            .order_by(BusinessDocument.uploaded_at.asc())
        )
    ).all()
    names = await masking.names_for_staff(db, admin, [b.id for _, b in rows], purpose="pending_documents")
    owners = {b.id: await get_owner(db, b.id) for _, b in rows}
    people = await masking.people_for_staff(
        db, admin, [o.id for o in owners.values() if o is not None], purpose="pending_documents"
    )
    out = []
    for d, b in rows:
        owner = owners[b.id]
        person = people.get(owner.id) if owner else None
        out.append(
            PendingDocRow(
                doc=doc_to_out(d, for_admin=True),
                user_id=str(owner.id) if owner else None,
                business_id=str(b.id),
                user_email=person.email if person else None,
                user_business_name=names.get(b.id),
                user_full_name=person.full_name if person else None,
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
    admin: Actor,
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
    doc.reviewed_by = admin.email
    doc.rejection_reason = reason if target == DocStatus.rejected else None
    record_action(
        db,
        admin=admin,
        action=f"doc.{'reject' if target == DocStatus.rejected else 'approve'}",
        target_type="document",
        target_id=doc.id,
        reason=reason if target == DocStatus.rejected else None,
        details={"businessId": str(doc.business_id), "docType": doc.doc_type},
    )
    contact = await owner_contact(db, doc.business_id)
    result = DocDecision(
        doc_id=doc.id,
        status=target,
        cert_type=doc.doc_type,
        owner_email=contact.email if contact else None,
        owner_name=contact.full_name if contact else None,
    )
    await db.commit()
    return result
