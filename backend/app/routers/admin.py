"""Admin console API — MVP.

Everything under `/admin/*` requires a signed session cookie issued by
`POST /admin/login`. Kept intentionally small after the email-auth rewrite;
the richer dashboard (funnels, duplicate alerts, verify queue) will be
rebuilt on top of the new schema in a follow-up.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import (
    ADMIN_COOKIE_NAME,
    AdminEmail,
    issue_session,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.user_session import _cookie_policy
from app.models.business_profile import BusinessProfile
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.models.verification_doc import DocStatus, VerificationDoc
from app.pii import mask_bank_account
from app.schemas.base import CamelModel
from app.verification import missing_mandatory_keys

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Auth endpoints ─────────────────────────────────────────────────────────


class LoginIn(BaseModel):
    email: str
    password: str


class LoginOut(CamelModel):
    email: str


@router.post("/login", response_model=LoginOut, response_model_by_alias=True)
async def admin_login(payload: LoginIn, response: Response) -> LoginOut:
    if payload.email.strip().lower() != settings.admin_email.strip().lower():
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = issue_session(settings.admin_email)
    # Cross-site cookie policy — shared with user_session._cookie_policy:
    # CROSS_SITE_COOKIES=true (HTTPS, frontend≠backend site) → SameSite=None;
    # Secure; local http dev → lax + insecure. Independent of DEBUG.
    samesite, secure = _cookie_policy()
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=settings.admin_session_max_age_hours * 3600,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )
    return LoginOut(email=settings.admin_email)


@router.post("/logout")
async def admin_logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=LoginOut, response_model_by_alias=True)
async def admin_me(email: AdminEmail) -> LoginOut:
    return LoginOut(email=email)


# ── Dashboard KPIs ─────────────────────────────────────────────────────────


class DashboardStats(CamelModel):
    total_users: int
    verified_users: int
    pending_verification_users: int
    active_users: int
    signed_up_users: int
    email_verified_users: int
    rejected_users: int
    total_products: int
    recent_signups_24h: int
    stuck_signups: int
    onboarded_users: int
    pending_docs: int


class TimelinePoint(CamelModel):
    date: str
    count: int


class StuckUser(CamelModel):
    user_id: str
    email: str
    business_name: str | None
    created_at: datetime
    hours_waiting: int


class VerifyDocOut(CamelModel):
    id: str
    cert_type: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    rejection_reason: str | None = None
    uploaded_at: datetime
    reviewed_at: datetime | None = None
    url: str


class PendingDocRow(CamelModel):
    """One pending document on the admin review queue."""

    doc: VerifyDocOut
    user_id: str
    user_email: str
    user_business_name: str | None
    user_full_name: str | None
    user_country: str | None


class VerifyQueueRow(CamelModel):
    user_id: str
    email: str
    full_name: str | None
    business_name: str | None
    country: str | None
    industry: str | None
    trade_position: str | None
    operating_countries: list[str] | None
    onboarded_at: datetime | None
    submitted_at: datetime | None
    created_at: datetime
    # Empty when the row is in the queue — the 7 fields are filled by
    # definition. Kept on the response so the admin UI can still render
    # a "fields filled" badge without a second request.
    missing_fields: list[str]
    docs: list[VerifyDocOut]


@router.get("/dashboard/stats", response_model=DashboardStats, response_model_by_alias=True)
async def dashboard_stats(
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    async def count_status(status: UserStatus) -> int:
        return await db.scalar(
            select(func.count(User.id)).where(
                User.status == status, User.deleted_at.is_(None)
            )
        ) or 0

    total_users = await db.scalar(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    ) or 0
    total_products = await db.scalar(select(func.count(Product.id))) or 0
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    recent = await db.scalar(
        select(func.count(User.id)).where(
            User.created_at >= since, User.deleted_at.is_(None)
        )
    ) or 0

    # Stuck signups — created > 24h ago but never verified their email.
    stuck_before = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    stuck = await db.scalar(
        select(func.count(User.id)).where(
            User.deleted_at.is_(None),
            User.email_verified_at.is_(None),
            User.created_at < stuck_before,
        )
    ) or 0

    onboarded = await db.scalar(
        select(func.count(BusinessProfile.user_id))
        .join(User, User.id == BusinessProfile.user_id)
        .where(
            User.deleted_at.is_(None),
            BusinessProfile.onboarded_at.is_not(None),
        )
    ) or 0

    pending_docs = await db.scalar(
        select(func.count(VerificationDoc.id)).where(
            VerificationDoc.status == DocStatus.pending
        )
    ) or 0

    return DashboardStats(
        total_users=total_users,
        verified_users=await count_status(UserStatus.verified),
        pending_verification_users=await count_status(UserStatus.pending_verification),
        active_users=await count_status(UserStatus.active),
        signed_up_users=await count_status(UserStatus.signed_up),
        email_verified_users=await count_status(UserStatus.email_verified),
        rejected_users=await count_status(UserStatus.rejected),
        total_products=total_products,
        recent_signups_24h=recent,
        stuck_signups=stuck,
        onboarded_users=onboarded,
        pending_docs=pending_docs,
    )


@router.get(
    "/dashboard/timeline",
    response_model=list[TimelinePoint],
    response_model_by_alias=True,
)
async def dashboard_timeline(
    _: AdminEmail,
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
) -> list[TimelinePoint]:
    """Daily signup counts for the last N days, oldest → newest.

    Returns every day in the window — including zero-count days — so the
    frontend doesn't have to fill gaps.
    """
    now = datetime.now(tz=timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    rows = await db.execute(
        select(
            func.date(User.created_at).label("day"),
            func.count(User.id),
        )
        .where(User.created_at >= start, User.deleted_at.is_(None))
        .group_by("day")
    )
    by_day: dict[str, int] = {str(day): count for day, count in rows.all()}

    out: list[TimelinePoint] = []
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        out.append(TimelinePoint(date=d, count=by_day.get(d, 0)))
    return out


@router.get(
    "/dashboard/stuck",
    response_model=list[StuckUser],
    response_model_by_alias=True,
)
async def dashboard_stuck(
    _: AdminEmail,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[StuckUser]:
    """Users who signed up but never verified their email after 24h+.

    Powers the "Stuck signups" card — the admin can nudge or email them.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    rows = await db.scalars(
        select(User)
        .where(
            User.deleted_at.is_(None),
            User.email_verified_at.is_(None),
            User.created_at < cutoff,
        )
        .order_by(User.created_at.asc())
        .limit(limit)
    )
    now = datetime.now(tz=timezone.utc)
    out: list[StuckUser] = []
    for u in rows:
        hours = int((now - u.created_at).total_seconds() // 3600)
        out.append(
            StuckUser(
                user_id=str(u.id),
                email=u.email,
                business_name=u.business_name,
                created_at=u.created_at,
                hours_waiting=hours,
            )
        )
    return out


@router.get(
    "/verify/queue",
    response_model=list[VerifyQueueRow],
    response_model_by_alias=True,
)
async def verify_queue(
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> list[VerifyQueueRow]:
    """Users awaiting admin verification review.

    Scope: anyone sitting in ``pending_verification`` — the backend
    flipped them here the first time all seven mandatory profile fields
    were filled. Rows carry uploaded KYB docs for the trust-score tier,
    but the badge decision only depends on the profile data itself.
    Oldest-submitted first so the queue stays fair.
    """
    rows = await db.execute(
        select(User, Profile, BusinessProfile)
        .outerjoin(BusinessProfile, BusinessProfile.user_id == User.id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(
            User.deleted_at.is_(None),
            User.status == UserStatus.pending_verification,
        )
        .order_by(User.verification_submitted_at.asc().nulls_last())
    )
    users = rows.all()
    if not users:
        return []

    user_ids = [u.id for u, _, _ in users]
    doc_rows = await db.scalars(
        select(VerificationDoc)
        .where(VerificationDoc.user_id.in_(user_ids))
        .order_by(VerificationDoc.uploaded_at.asc())
    )
    docs_by_user: dict[uuid.UUID, list[VerifyDocOut]] = {}
    for d in doc_rows:
        docs_by_user.setdefault(d.user_id, []).append(_doc_dto(d))

    out: list[VerifyQueueRow] = []
    for u, prof, biz in users:
        out.append(
            VerifyQueueRow(
                user_id=str(u.id),
                email=u.email,
                full_name=prof.full_name if prof else None,
                business_name=u.business_name,
                country=prof.country if prof else None,
                industry=biz.industry if biz else None,
                trade_position=biz.trade_position if biz else None,
                operating_countries=biz.operating_countries if biz else None,
                onboarded_at=biz.onboarded_at if biz else None,
                submitted_at=u.verification_submitted_at,
                created_at=u.created_at,
                missing_fields=missing_mandatory_keys(prof, biz),
                docs=docs_by_user.get(u.id, []),
            )
        )
    return out


# ── User list ──────────────────────────────────────────────────────────────


class UserRow(CamelModel):
    user_id: str
    email: str
    business_name: str | None
    status: str
    email_verified: bool
    has_password: bool
    created_at: datetime


class UserList(CamelModel):
    total: int
    items: list[UserRow]


@router.get("/users", response_model=UserList, response_model_by_alias=True)
async def admin_users(
    _: AdminEmail,
    q: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> UserList:
    stmt = select(User).where(User.deleted_at.is_(None))
    if status:
        try:
            stmt = stmt.where(User.status == UserStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Unknown status")
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(User.email.ilike(pattern), User.business_name.ilike(pattern))
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        await db.scalars(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit))
    )
    items = [
        UserRow(
            user_id=str(u.id),
            email=u.email,
            business_name=u.business_name,
            status=u.status.value,
            email_verified=u.email_verified_at is not None,
            has_password=u.password_hash is not None,
            created_at=u.created_at,
        )
        for u in rows
    ]
    return UserList(total=total, items=items)


# ── User detail ────────────────────────────────────────────────────────────


class UserDetail(CamelModel):
    user_id: str
    email: str
    email_verified_at: datetime | None
    business_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    has_password: bool
    profile: dict[str, Any] | None
    business_profile: dict[str, Any] | None
    product_count: int
    docs: list[VerifyDocOut]
    # ─── Verification audit (powers the review band at the top of the
    #     admin user-detail page). ``missing_mandatory_fields`` lets the
    #     UI tell the admin which fields are still blank, in which case
    #     the Approve button is disabled — the user shouldn't be in
    #     ``pending_verification`` with blanks, but we double-check on
    #     render in case an admin edited them away.
    verification_submitted_at: datetime | None
    verified_at: datetime | None
    verification_rejected_reason: str | None
    missing_mandatory_fields: list[str]


class UserPatchIn(CamelModel):
    """Fields the admin can edit directly on a user's account.

    Everything is optional; only present keys are applied. The admin can
    change the human-readable business name, personal profile fields, and
    free-text business metadata. Status flips (verify/reject) use their
    dedicated endpoints so the audit intent stays clear.
    """

    business_name: str | None = None
    profile: dict[str, Any] | None = None
    business_profile: dict[str, Any] | None = None


def _doc_dto(d: VerificationDoc) -> VerifyDocOut:
    return VerifyDocOut(
        id=str(d.id),
        cert_type=d.cert_type,
        filename=d.filename,
        mime_type=d.mime_type,
        size_bytes=d.size_bytes,
        status=d.status.value,
        rejection_reason=d.rejection_reason,
        uploaded_at=d.uploaded_at,
        reviewed_at=d.reviewed_at,
        url=f"/uploads/verification/{d.stored_path}",
    )


def _profile_dict(profile: Profile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "fullName": profile.full_name,
        "phone": profile.phone,
        "department": profile.department,
        "position": profile.position,
        "addressLine": profile.address_line,
        "city": profile.city,
        "state": profile.state,
        "pincode": profile.pincode,
        "country": profile.country,
        "websiteUrl": profile.website_url,
        "googleBusinessUrl": profile.google_business_url,
        "facebookUrl": profile.facebook_url,
    }


def _business_dict(business: BusinessProfile | None) -> dict[str, Any] | None:
    if business is None:
        return None
    return {
        "legalName": business.legal_name,
        "industry": business.industry,
        "operatingCountries": business.operating_countries,
        "websiteUrl": business.website_url,
        "tradePosition": business.trade_position,
        "sellerType": business.seller_type,
        "businessRole": business.business_role,
        "exportStatus": business.export_status,
        "targetMarkets": business.target_markets,
        "targetBuyerTypes": business.target_buyer_types,
        "mainObjective": business.main_objective,
        "companyIntroduction": business.company_introduction,
        "businessType": business.business_type,
        "natureOfBusiness": business.nature_of_business,
        "udyam": business.udyam,
        # Bank is masked at the API boundary — admin never sees the full number.
        "bankAccountNumber": mask_bank_account(business.bank_account_number),
        "bankIfsc": business.bank_ifsc,
        "bankHolderName": business.bank_holder_name,
        "bankBranchName": business.bank_branch_name,
        "bankName": business.bank_name,
        "onboardedAt": business.onboarded_at.isoformat() if business.onboarded_at else None,
    }


async def _load_user_detail(db: AsyncSession, uid: uuid.UUID) -> UserDetail:
    # Freshly SELECT the user — db.get() may return a half-expired instance
    # after a commit, which would try to lazy-load updated_at synchronously
    # and crash with MissingGreenlet.
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    profile = await db.scalar(select(Profile).where(Profile.user_id == uid))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == uid)
    )
    product_count = await db.scalar(
        select(func.count(Product.id)).where(Product.user_id == uid)
    ) or 0
    doc_rows = await db.scalars(
        select(VerificationDoc)
        .where(VerificationDoc.user_id == uid)
        .order_by(VerificationDoc.uploaded_at.desc())
    )
    docs = [_doc_dto(d) for d in doc_rows]

    return UserDetail(
        user_id=str(user.id),
        email=user.email,
        email_verified_at=user.email_verified_at,
        business_name=user.business_name,
        status=user.status.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
        has_password=user.password_hash is not None,
        profile=_profile_dict(profile),
        business_profile=_business_dict(business),
        product_count=product_count,
        docs=docs,
        verification_submitted_at=user.verification_submitted_at,
        verified_at=user.verified_at,
        verification_rejected_reason=user.verification_rejected_reason,
        missing_mandatory_fields=missing_mandatory_keys(profile, business),
    )


@router.get("/users/{user_id}", response_model=UserDetail, response_model_by_alias=True)
async def admin_user_detail(
    user_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None
    return await _load_user_detail(db, uid)


# Keys the admin is allowed to overwrite via PATCH. Everything else in the
# incoming dict is silently dropped so a hostile payload can't flip columns
# the admin shouldn't touch (e.g. password_hash, email_verified_at, bank_*).
_PROFILE_EDITABLE_KEYS = {
    "fullName",
    "phone",
    "department",
    "position",
    "addressLine",
    "city",
    "state",
    "pincode",
    "country",
    "websiteUrl",
    "googleBusinessUrl",
    "facebookUrl",
}
_BUSINESS_EDITABLE_KEYS = {
    "legalName",
    "industry",
    "operatingCountries",
    "websiteUrl",
    "tradePosition",
    "sellerType",
    "businessRole",
    "exportStatus",
    "targetMarkets",
    "targetBuyerTypes",
    "mainObjective",
    "companyIntroduction",
    "businessType",
    "natureOfBusiness",
    "udyam",
}
# camelCase → snake_case for the Profile model
_PROFILE_FIELD_MAP = {
    "fullName": "full_name",
    "phone": "phone",
    "department": "department",
    "position": "position",
    "addressLine": "address_line",
    "city": "city",
    "state": "state",
    "pincode": "pincode",
    "country": "country",
    "websiteUrl": "website_url",
    "googleBusinessUrl": "google_business_url",
    "facebookUrl": "facebook_url",
}
_BUSINESS_FIELD_MAP = {
    "legalName": "legal_name",
    "industry": "industry",
    "operatingCountries": "operating_countries",
    "websiteUrl": "website_url",
    "tradePosition": "trade_position",
    "sellerType": "seller_type",
    "businessRole": "business_role",
    "exportStatus": "export_status",
    "targetMarkets": "target_markets",
    "targetBuyerTypes": "target_buyer_types",
    "mainObjective": "main_objective",
    "companyIntroduction": "company_introduction",
    "businessType": "business_type",
    "natureOfBusiness": "nature_of_business",
    "udyam": "udyam",
}


@router.patch("/users/{user_id}", response_model=UserDetail, response_model_by_alias=True)
async def admin_user_patch(
    user_id: str,
    payload: UserPatchIn,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    """Admin edit for a user's profile fields.

    Only whitelisted keys from the payload are applied — see
    ``_PROFILE_EDITABLE_KEYS`` and ``_BUSINESS_EDITABLE_KEYS``. Verify / reject
    continue to use their own endpoints so the audit log can distinguish an
    identity edit from a status change.
    """
    uid = _parse_uid(user_id)

    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.business_name is not None:
        user.business_name = payload.business_name.strip() or None

    if payload.profile:
        profile = await db.scalar(select(Profile).where(Profile.user_id == uid))
        if profile is None:
            # Can't create a profile without a full_name — require it in the payload.
            full = (payload.profile.get("fullName") or "").strip()
            if not full:
                raise HTTPException(
                    status_code=400,
                    detail="This user has no profile yet. Include fullName to create one.",
                )
            profile = Profile(user_id=uid, full_name=full)
            db.add(profile)
        for key, val in payload.profile.items():
            if key not in _PROFILE_EDITABLE_KEYS:
                continue
            attr = _PROFILE_FIELD_MAP[key]
            setattr(profile, attr, val if val != "" else None)

    if payload.business_profile:
        business = await db.scalar(
            select(BusinessProfile).where(BusinessProfile.user_id == uid)
        )
        if business is None:
            business = BusinessProfile(user_id=uid)
            db.add(business)
        for key, val in payload.business_profile.items():
            if key not in _BUSINESS_EDITABLE_KEYS:
                continue
            attr = _BUSINESS_FIELD_MAP[key]
            setattr(business, attr, val if val != "" else None)

    # Submission to the verification queue is now a user-initiated
    # action — admin edits only persist the data. The admin can still
    # move the user manually via the Approve / Reject buttons on this
    # page if they want to short-circuit the review.
    await db.commit()
    return await _load_user_detail(db, uid)


# ── Verify / reject actions ────────────────────────────────────────────────


class StatusChanged(CamelModel):
    user_id: str
    status: str


class UserRejectIn(CamelModel):
    """Admin's note when rejecting a Verified-badge application.

    The user sees this verbatim in a popup on their next login, so the
    admin should spell out what to fix — not just that it was rejected.
    """

    reason: str


def _parse_uid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None


@router.post("/users/{user_id}/verify", response_model=StatusChanged, response_model_by_alias=True)
async def admin_verify(
    user_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> StatusChanged:
    """Approve a user: flip to ``verified``, stamp ``verified_at``.

    Clears any lingering rejection reason so a previously-rejected user
    who fixed their profile and got re-approved doesn't still see the
    old admin note on their next login.
    """
    uid = _parse_uid(user_id)
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.verified
    user.verified_at = datetime.now(tz=timezone.utc)
    user.verification_rejected_reason = None
    await db.commit()
    return StatusChanged(user_id=str(user.id), status=user.status.value)


@router.post("/users/{user_id}/reject", response_model=StatusChanged, response_model_by_alias=True)
async def admin_reject(
    user_id: str,
    payload: UserRejectIn,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> StatusChanged:
    """Reject a Verified-badge application with a mandatory reason."""
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="A rejection reason is required so the user knows what to fix.",
        )
    if len(reason) > 500:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is too long (500 chars max).",
        )
    uid = _parse_uid(user_id)
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.rejected
    user.verification_rejected_reason = reason
    await db.commit()
    return StatusChanged(user_id=str(user.id), status=user.status.value)


# ── Per-document review ────────────────────────────────────────────────────


class DocStatusChanged(CamelModel):
    doc_id: str
    status: str


class DocRejectIn(CamelModel):
    reason: str


@router.get(
    "/docs/pending",
    response_model=list[PendingDocRow],
    response_model_by_alias=True,
)
async def admin_docs_pending(
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> list[PendingDocRow]:
    """Every document still awaiting admin review, oldest-first."""
    doc_rows = list(
        await db.scalars(
            select(VerificationDoc)
            .where(VerificationDoc.status == DocStatus.pending)
            .order_by(VerificationDoc.uploaded_at.asc())
        )
    )
    if not doc_rows:
        return []
    uids = list({d.user_id for d in doc_rows})
    users = {
        u.id: u
        for u in await db.scalars(select(User).where(User.id.in_(uids)))
    }
    profiles = {
        p.user_id: p
        for p in await db.scalars(select(Profile).where(Profile.user_id.in_(uids)))
    }
    out: list[PendingDocRow] = []
    for d in doc_rows:
        u = users.get(d.user_id)
        if u is None or u.deleted_at is not None:
            continue
        p = profiles.get(d.user_id)
        out.append(
            PendingDocRow(
                doc=_doc_dto(d),
                user_id=str(u.id),
                user_email=u.email,
                user_business_name=u.business_name,
                user_full_name=p.full_name if p else None,
                user_country=p.country if p else None,
            )
        )
    return out


@router.post(
    "/docs/{doc_id}/approve",
    response_model=DocStatusChanged,
    response_model_by_alias=True,
)
async def admin_doc_approve(
    doc_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> DocStatusChanged:
    doc = await _flip_doc(db, doc_id, DocStatus.approved)
    return DocStatusChanged(doc_id=str(doc.id), status=doc.status.value)


@router.post(
    "/docs/{doc_id}/reject",
    response_model=DocStatusChanged,
    response_model_by_alias=True,
)
async def admin_doc_reject(
    doc_id: str,
    payload: DocRejectIn,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> DocStatusChanged:
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="A rejection reason is required so the user knows what to fix.",
        )
    if len(reason) > 500:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is too long (500 chars max).",
        )
    doc = await _flip_doc(db, doc_id, DocStatus.rejected, reason=reason)
    return DocStatusChanged(doc_id=str(doc.id), status=doc.status.value)


async def _flip_doc(
    db: AsyncSession,
    doc_id: str,
    target: DocStatus,
    *,
    reason: str | None = None,
) -> VerificationDoc:
    try:
        did = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found") from None
    doc = await db.get(VerificationDoc, did)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = target
    doc.reviewed_at = datetime.now(tz=timezone.utc)
    # Only touch rejection_reason when actually rejecting — approving the
    # same doc later clears it so the stale reason doesn't linger.
    doc.rejection_reason = reason if target == DocStatus.rejected else None
    await db.commit()
    await db.refresh(doc)
    return doc
