"""Admin console API — single-operator MVP.

Everything under `/admin/*` requires a signed session cookie issued by
`POST /admin/login`. Read-only for now: verify/ban/warn actions land after
this dashboard is validated.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
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
from app.models.business_profile import BusinessProfile, OnboardingPath
from app.models.contact_reveal import ContactReveal
from app.models.identity import Identity
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.pii import mask_aadhaar, mask_bank_account
from app.schemas.base import CamelModel
from app.schemas.reveal import AdminRecentReveal

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
    # Cross-site cookie policy — same rationale as user_session._cookie_policy:
    # prod (DEBUG=false) → SameSite=None; Secure so the cookie flows from the
    # frontend to the API across different *.up.railway.app sites over HTTPS;
    # dev (DEBUG=true) → lax + insecure for same-origin localhost.
    samesite = "lax" if settings.debug else "none"
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=settings.admin_session_max_age_hours * 3600,
        httponly=True,
        samesite=samesite,
        secure=not settings.debug,
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


# ── Helpers ────────────────────────────────────────────────────────────────


async def _primary_mobile(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    """Primary identity for a user — the numeric one (phone) if present,
    otherwise the first identity value in DB order."""
    rows = await db.scalars(
        select(Identity.value).where(Identity.user_id == user_id)
    )
    vals = list(rows)
    for v in vals:
        if v and v.isdigit():
            return v
    return vals[0] if vals else None


def _stage(profile: Profile | None, business: BusinessProfile | None) -> str:
    """Bucket a user into the verification funnel. Bank now lives on the
    same `business_profiles` row, so no separate arg."""
    primary = bool(
        profile
        and profile.full_name
        and profile.email
        and profile.address_line
        and profile.city
        and profile.state
        and profile.pincode
    )
    biz = bool(business and business.pan and business.company_name)
    bank_ok = bool(
        business
        and business.bank_account_number
        and business.bank_ifsc
        and business.bank_holder_name
    )
    if primary and biz and bank_ok:
        return "verified"
    if primary and biz:
        return "bank_pending"
    if primary:
        return "business_pending"
    if profile and profile.full_name:
        return "primary_pending"
    return "signed_up"


# ── Dashboard: stats ───────────────────────────────────────────────────────


class DashboardStats(CamelModel):
    total_buyers: int
    total_sellers: int
    total_verified: int
    signups_this_week: int
    signups_prev_week: int
    funnel: dict[str, int]  # stage → count
    top_states: dict[str, list[dict[str, Any]]]  # {"buyer": [...], "seller": [...]}
    duplicate_alerts: list[dict[str, Any]]


@router.get(
    "/dashboard/stats",
    response_model=DashboardStats,
    response_model_by_alias=True,
)
async def dashboard_stats(
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    total_users = await db.scalar(select(func.count(User.id))) or 0
    # Sellers are users with at least one product — count distinct product owners.
    seller_ids = {
        r for r in await db.scalars(select(Product.user_id).distinct())
    }
    total_sellers = len(seller_ids)
    total_buyers = total_users - total_sellers
    total_verified = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.verified)
    ) or 0

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    signups_this_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    ) or 0
    signups_prev_week = await db.scalar(
        select(func.count(User.id)).where(
            User.created_at >= two_weeks_ago, User.created_at < week_ago
        )
    ) or 0

    # Funnel — one pass over users + their profile/business rows.
    users = list(await db.scalars(select(User)))
    profiles_map = {p.user_id: p for p in await db.scalars(select(Profile))}
    business_map = {
        b.user_id: b for b in await db.scalars(select(BusinessProfile))
    }
    funnel_counter: Counter[str] = Counter()
    for u in users:
        funnel_counter[
            _stage(profiles_map.get(u.id), business_map.get(u.id))
        ] += 1
    funnel = {
        "signed_up": funnel_counter.get("signed_up", 0),
        "primary_pending": funnel_counter.get("primary_pending", 0),
        "business_pending": funnel_counter.get("business_pending", 0),
        "bank_pending": funnel_counter.get("bank_pending", 0),
        "verified": funnel_counter.get("verified", 0),
    }

    # Top states — buyers vs sellers. Role is derived from seller_ids.
    state_buckets: dict[str, Counter[str]] = {"buyer": Counter(), "seller": Counter()}
    for p in profiles_map.values():
        if not p.state:
            continue
        role = "seller" if p.user_id in seller_ids else "buyer"
        state_buckets[role][p.state.strip().title()] += 1
    top_states = {
        role: [{"state": s, "count": c} for s, c in bucket.most_common(5)]
        for role, bucket in state_buckets.items()
    }

    # Duplicate GSTIN / PAN alerts — labelled by name (fallback: mobile).
    async def _label(uid: uuid.UUID) -> str:
        p = profiles_map.get(uid)
        if p and p.full_name:
            return p.full_name
        mobile = await _primary_mobile(db, uid)
        return mobile or str(uid)[:8]

    def _people(ids: list[uuid.UUID]) -> list[dict[str, str]]:
        seen: set[uuid.UUID] = set()
        return [
            {"user_id": str(i)}
            for i in ids
            if not (i in seen or seen.add(i))
        ]

    gstin_map: dict[str, list[uuid.UUID]] = defaultdict(list)
    pan_map: dict[str, list[uuid.UUID]] = defaultdict(list)
    for bp in business_map.values():
        if bp.gstin:
            gstin_map[bp.gstin.strip().upper()].append(bp.user_id)
        if bp.pan:
            pan_map[bp.pan.strip().upper()].append(bp.user_id)
    duplicate_alerts: list[dict[str, Any]] = []
    for gstin, ids in gstin_map.items():
        if len(ids) > 1:
            people = _people(ids)
            for pl in people:
                pl["label"] = await _label(uuid.UUID(pl["user_id"]))
            duplicate_alerts.append({"kind": "GSTIN", "value": gstin, "users": people})
    for pan, ids in pan_map.items():
        if len(ids) > 1:
            people = _people(ids)
            for pl in people:
                pl["label"] = await _label(uuid.UUID(pl["user_id"]))
            duplicate_alerts.append({"kind": "PAN", "value": pan, "users": people})

    return DashboardStats(
        total_buyers=total_buyers,
        total_sellers=total_sellers,
        total_verified=total_verified,
        signups_this_week=signups_this_week,
        signups_prev_week=signups_prev_week,
        funnel=funnel,
        top_states=top_states,
        duplicate_alerts=duplicate_alerts,
    )


# ── Dashboard: onboarding timeline ─────────────────────────────────────────


class TimelinePoint(CamelModel):
    date: str  # YYYY-MM-DD
    buyer: int
    seller: int


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
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    users = list(
        await db.scalars(select(User).where(User.created_at >= start))
    )
    seller_ids = {
        r for r in await db.scalars(select(Product.user_id).distinct())
    }
    buckets: dict[str, dict[str, int]] = {}
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[d] = {"buyer": 0, "seller": 0}
    for u in users:
        key = u.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if key in buckets:
            role = "seller" if u.id in seller_ids else "buyer"
            buckets[key][role] += 1
    return [
        TimelinePoint(date=d, buyer=v["buyer"], seller=v["seller"])
        for d, v in buckets.items()
    ]


# ── Dashboard: recent signups feed ─────────────────────────────────────────


class RecentSignup(CamelModel):
    user_id: str
    full_name: str | None
    user_type: str
    status: str
    created_at: datetime
    mobile: str | None


@router.get(
    "/dashboard/reveals",
    response_model=list[AdminRecentReveal],
    response_model_by_alias=True,
)
async def dashboard_reveals(
    _: AdminEmail,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[AdminRecentReveal]:
    """Recent contact reveals — signal that the funnel is working."""
    rows = list(
        await db.scalars(
            select(ContactReveal)
            .order_by(ContactReveal.revealed_at.desc())
            .limit(limit)
        )
    )
    if not rows:
        return []

    buyer_ids = {r.buyer_id for r in rows}
    seller_ids = {r.seller_id for r in rows}
    product_ids = {r.product_id for r in rows}

    profiles = {
        p.user_id: p
        for p in await db.scalars(
            select(Profile).where(Profile.user_id.in_(buyer_ids))
        )
    }
    businesses = {
        b.user_id: b
        for b in await db.scalars(
            select(BusinessProfile).where(BusinessProfile.user_id.in_(seller_ids))
        )
    }
    products = {
        p.id: p
        for p in await db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        )
    }

    return [
        AdminRecentReveal(
            reveal_id=str(r.id),
            buyer_id=str(r.buyer_id),
            buyer_name=(profiles.get(r.buyer_id).full_name if profiles.get(r.buyer_id) else None),
            seller_id=str(r.seller_id),
            seller_company=(
                businesses.get(r.seller_id).company_name
                if businesses.get(r.seller_id)
                else None
            ),
            product_id=str(r.product_id),
            product_name=(products.get(r.product_id).name if products.get(r.product_id) else "(deleted)"),
            revealed_at=r.revealed_at,
        )
        for r in rows
    ]


@router.get(
    "/dashboard/recent",
    response_model=list[RecentSignup],
    response_model_by_alias=True,
)
async def dashboard_recent(
    _: AdminEmail,
    limit: int = Query(8, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[RecentSignup]:
    users = list(
        await db.scalars(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
    )
    seller_ids = {
        r for r in await db.scalars(select(Product.user_id).distinct())
    }
    result: list[RecentSignup] = []
    for u in users:
        profile = await db.scalar(select(Profile).where(Profile.user_id == u.id))
        mobile = await _primary_mobile(db, u.id)
        result.append(
            RecentSignup(
                user_id=str(u.id),
                full_name=profile.full_name if profile else None,
                user_type="seller" if u.id in seller_ids else "buyer",
                status=u.status.value,
                created_at=u.created_at,
                mobile=mobile,
            )
        )
    return result


# ── Users list ────────────────────────────────────────────────────────────


class UserRow(CamelModel):
    user_id: str
    full_name: str | None
    user_type: str
    status: str
    stage: str
    mobile: str | None
    email: str | None
    state: str | None
    created_at: datetime


class UsersListOut(CamelModel):
    total: int
    items: list[UserRow]


@router.get(
    "/users",
    response_model=UsersListOut,
    response_model_by_alias=True,
)
async def admin_users(
    _: AdminEmail,
    user_type: str | None = Query(None, alias="type"),
    status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> UsersListOut:
    stmt = select(User)
    if status in {s.value for s in UserStatus}:
        stmt = stmt.where(User.status == UserStatus(status))

    all_users = list(await db.scalars(stmt.order_by(User.created_at.desc())))
    profiles_map = {p.user_id: p for p in await db.scalars(select(Profile))}
    business_map = {
        b.user_id: b for b in await db.scalars(select(BusinessProfile))
    }
    seller_ids = {
        r for r in await db.scalars(select(Product.user_id).distinct())
    }
    identities_by_user: dict[uuid.UUID, list[str]] = defaultdict(list)
    for ident in await db.scalars(select(Identity)):
        identities_by_user[ident.user_id].append(ident.value)

    # Role filter — derived, not stored.
    if user_type == "buyer":
        all_users = [u for u in all_users if u.id not in seller_ids]
    elif user_type == "seller":
        all_users = [u for u in all_users if u.id in seller_ids]

    def matches_q(u: User) -> bool:
        if not q:
            return True
        needle = q.strip().lower()
        p = profiles_map.get(u.id)
        bp = business_map.get(u.id)
        haystack: list[str] = []
        if p:
            if p.full_name:
                haystack.append(p.full_name)
            if p.email:
                haystack.append(p.email)
        if bp:
            if bp.gstin:
                haystack.append(bp.gstin)
            if bp.pan:
                haystack.append(bp.pan)
            if bp.company_name:
                haystack.append(bp.company_name)
        haystack.extend(identities_by_user.get(u.id, []))
        return any(needle in v.lower() for v in haystack)

    filtered = [u for u in all_users if matches_q(u)]
    total = len(filtered)
    page = filtered[offset : offset + limit]

    items: list[UserRow] = []
    for u in page:
        p = profiles_map.get(u.id)
        bp = business_map.get(u.id)
        idents = identities_by_user.get(u.id, [])
        mobile = next((v for v in idents if v.isdigit()), None)
        items.append(
            UserRow(
                user_id=str(u.id),
                full_name=p.full_name if p else None,
                user_type="seller" if u.id in seller_ids else "buyer",
                status=u.status.value,
                stage=_stage(p, bp),
                mobile=mobile,
                email=(p.email if p else None),
                state=p.state if p else None,
                created_at=u.created_at,
            )
        )
    return UsersListOut(total=total, items=items)


# ── User detail ────────────────────────────────────────────────────────────


class UserDetail(CamelModel):
    user_id: str
    user_type: str
    status: str
    stage: str
    created_at: datetime
    updated_at: datetime
    mobile: str | None
    has_buyer_data: bool
    has_seller_data: bool
    buyer: dict[str, Any] | None
    seller: dict[str, Any] | None
    bank: dict[str, Any] | None


async def _load_user_detail(db: AsyncSession, uid: uuid.UUID) -> UserDetail:
    user = await db.scalar(select(User).where(User.id == uid))
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    profile = await db.scalar(select(Profile).where(Profile.user_id == uid))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == uid)
    )
    mobile = await _primary_mobile(db, uid)
    product_count = await db.scalar(
        select(func.count(Product.id)).where(Product.user_id == uid)
    ) or 0

    # "buyer" block = personal profile — kept as buyer JSON key for the pulled
    # admin UI which still expects that shape.
    buyer_block: dict[str, Any] | None = None
    if profile:
        buyer_block = {
            "fullName": profile.full_name,
            "email": profile.email,
            "addressLine": profile.address_line,
            "city": profile.city,
            "state": profile.state,
            "pincode": profile.pincode,
            "country": profile.country,
            "altMobile": profile.alt_mobile,
            "altEmail": profile.alt_email,
            "businessEmail": profile.business_email,
            "websiteUrl": profile.website_url,
        }
    seller_block: dict[str, Any] | None = None
    bank_block: dict[str, Any] | None = None
    if business:
        seller_block = {
            "onboardingPath": business.onboarding_path.value,
            "gstin": business.gstin,
            "pan": business.pan,
            "companyName": business.company_name,
            "businessType": business.business_type,
            "natureOfBusiness": business.nature_of_business,
            "udyam": business.udyam,
            # PII: mask Aadhaar even in the admin view. Admin sees last 4
            # for identification; ops that need the full value read the DB.
            "aadhaar": mask_aadhaar(business.aadhaar),
            "tan": business.tan,
        }
        # Only surface the bank block once any of the fields is populated.
        if any(
            (
                business.bank_account_number,
                business.bank_ifsc,
                business.bank_holder_name,
            )
        ):
            bank_block = {
                "accountNumber": mask_bank_account(business.bank_account_number),
                "ifsc": business.bank_ifsc,
                "holderName": business.bank_holder_name,
                "branchName": business.bank_branch_name,
                "bankName": business.bank_name,
            }

    return UserDetail(
        user_id=str(user.id),
        user_type="seller" if product_count > 0 else "buyer",
        status=user.status.value,
        stage=_stage(profile, business),
        created_at=user.created_at,
        updated_at=user.updated_at,
        mobile=mobile,
        has_buyer_data=bool(profile and profile.full_name),
        has_seller_data=bool(business),
        buyer=buyer_block,
        seller=seller_block,
        bank=bank_block,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserDetail,
    response_model_by_alias=True,
)
async def admin_user_detail(
    user_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None
    return await _load_user_detail(db, uid)


# ── User update (admin edits) ─────────────────────────────────────────────


def _blank_to_none(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class AdminBuyerPatch(CamelModel):
    """Personal profile fields — writes to `profiles`."""

    full_name: str | None = None
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    alt_mobile: str | None = None
    alt_email: str | None = None
    business_email: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class AdminSellerPatch(CamelModel):
    """Business identity fields — writes to `business_profiles`."""

    gstin: str | None = None
    pan: str | None = None
    company_name: str | None = None
    business_type: str | None = None
    nature_of_business: str | None = None
    udyam: str | None = None
    aadhaar: str | None = None
    tan: str | None = None


class AdminBankPatch(CamelModel):
    """Bank fields — writes to `business_profiles.bank_*` (was separate table)."""

    account_number: str | None = None
    ifsc: str | None = None
    holder_name: str | None = None
    branch_name: str | None = None
    bank_name: str | None = None


class AdminUserPatch(CamelModel):
    buyer: AdminBuyerPatch | None = None
    seller: AdminSellerPatch | None = None
    bank: AdminBankPatch | None = None


def _apply_profile_patch(profile: Profile, patch: AdminBuyerPatch) -> None:
    """Copy every field the admin sent onto the profile row. Empty string
    clears a nullable field; None means 'don't touch this key'. full_name is
    required, so blanking is ignored."""
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if field == "full_name":
            if cleaned:
                profile.full_name = cleaned
            continue
        if field == "country" and cleaned is None:
            # country has a NOT NULL server default — don't accept a blank
            continue
        setattr(profile, field, cleaned)


def _apply_business_patch(business: BusinessProfile, patch: AdminSellerPatch) -> None:
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if cleaned and field in {"pan", "gstin"}:
            cleaned = cleaned.upper()
        # pan / company_name are NOT NULL — silently drop attempts to blank
        if cleaned is None and field in {"pan", "company_name"}:
            continue
        setattr(business, field, cleaned)


def _apply_bank_patch(business: BusinessProfile, patch: AdminBankPatch) -> None:
    """Bank fields sit on business_profiles under a `bank_` prefix."""
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if cleaned and field == "ifsc":
            cleaned = cleaned.upper()
        # Map: account_number → bank_account_number etc.
        setattr(business, f"bank_{field}", cleaned)


@router.patch(
    "/users/{user_id}",
    response_model=UserDetail,
    response_model_by_alias=True,
)
async def admin_user_patch(
    user_id: str,
    payload: AdminUserPatch,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None
    user = await db.scalar(select(User).where(User.id == uid))
    if not user:
        raise HTTPException(status_code=404, detail="Not found")

    if payload.buyer is not None:
        profile = await db.scalar(select(Profile).where(Profile.user_id == uid))
        if profile is None:
            name = _blank_to_none(payload.buyer.full_name)
            if not name:
                raise HTTPException(
                    status_code=400,
                    detail="Full name is required to create a profile",
                )
            profile = Profile(user_id=uid, full_name=name)
            db.add(profile)
        _apply_profile_patch(profile, payload.buyer)

    if payload.seller is not None:
        business = await db.scalar(
            select(BusinessProfile).where(BusinessProfile.user_id == uid)
        )
        if business is None:
            # BusinessProfile has NOT NULL onboarding_path, pan, company_name.
            # Guard: refuse creation unless all three are in the payload.
            pan = _blank_to_none(payload.seller.pan)
            company = _blank_to_none(payload.seller.company_name)
            if not (pan and company):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot create business profile without PAN and "
                        "company name"
                    ),
                )
            gstin = _blank_to_none(payload.seller.gstin)
            business = BusinessProfile(
                user_id=uid,
                onboarding_path=(
                    OnboardingPath.gstin if gstin else OnboardingPath.pan
                ),
                gstin=gstin.upper() if gstin else None,
                pan=pan.upper(),
                company_name=company,
            )
            db.add(business)
        _apply_business_patch(business, payload.seller)

    if payload.bank is not None:
        business = await db.scalar(
            select(BusinessProfile).where(BusinessProfile.user_id == uid)
        )
        if business is None:
            raise HTTPException(
                status_code=400,
                detail="Fill business profile before setting bank details",
            )
        _apply_bank_patch(business, payload.bank)

    # Re-run "all-three-complete → verified" gate after admin edits.
    await db.flush()
    profile2 = await db.scalar(select(Profile).where(Profile.user_id == uid))
    business2 = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == uid)
    )
    if (
        _stage(profile2, business2) == "verified"
        and user.status != UserStatus.verified
    ):
        user.status = UserStatus.verified

    await db.commit()
    return await _load_user_detail(db, uid)


# ── Quick-action verify / reject (Sprint 4) ────────────────────────────────


async def _flip_status(user: User, target: UserStatus) -> None:
    """Set status. `updated_at` is auto-bumped by SQLAlchemy onupdate —
    that timestamp is what the queue's dwell chip reads from."""
    user.status = target


async def _flip_by_id(db: AsyncSession, uid: uuid.UUID, target: UserStatus) -> User:
    user = await db.scalar(select(User).where(User.id == uid))
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    await _flip_status(user, target)
    return user


@router.post(
    "/users/{user_id}/verify",
    response_model=UserDetail,
    response_model_by_alias=True,
)
async def admin_verify_user(
    user_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None
    await _flip_by_id(db, uid, UserStatus.verified)
    await db.commit()
    return await _load_user_detail(db, uid)


@router.post(
    "/users/{user_id}/reject",
    response_model=UserDetail,
    response_model_by_alias=True,
)
async def admin_reject_user(
    user_id: str,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None
    await _flip_by_id(db, uid, UserStatus.rejected)
    await db.commit()
    return await _load_user_detail(db, uid)


class BulkVerifyIn(CamelModel):
    user_ids: list[str]


class BulkVerifyOut(CamelModel):
    verified: int
    skipped: list[str]


@router.post(
    "/users/bulk-verify",
    response_model=BulkVerifyOut,
    response_model_by_alias=True,
)
async def admin_bulk_verify(
    payload: BulkVerifyIn,
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> BulkVerifyOut:
    """Flip many users to verified in one call. Silently skips ids that
    don't parse, don't exist, or are already deleted — returns the list
    of skipped ids so the UI can flag partial success."""
    if not payload.user_ids:
        return BulkVerifyOut(verified=0, skipped=[])
    parsed: list[uuid.UUID] = []
    skipped: list[str] = []
    for raw in payload.user_ids:
        try:
            parsed.append(uuid.UUID(raw))
        except ValueError:
            skipped.append(raw)

    users = list(
        await db.scalars(
            select(User).where(User.id.in_(parsed), User.deleted_at.is_(None))
        )
    )
    found_ids = {u.id for u in users}
    for raw, pid in zip(payload.user_ids, parsed):
        if pid not in found_ids:
            skipped.append(raw)
    for u in users:
        await _flip_status(u, UserStatus.verified)
    await db.commit()
    return BulkVerifyOut(verified=len(users), skipped=skipped)


# ── Verification queue ────────────────────────────────────────────────────


class QueueRow(CamelModel):
    user_id: str
    full_name: str | None
    mobile: str | None
    company_name: str | None
    state: str | None
    dwell_days: int
    updated_at: datetime


class VerificationQueue(CamelModel):
    """Users grouped by where they're stuck. Sorted oldest-first per group
    (biggest dwell at top) so admin's eye lands on the most-neglected user."""

    signed_up: list[QueueRow]
    primary_pending: list[QueueRow]
    business_pending: list[QueueRow]
    bank_pending: list[QueueRow]


@router.get(
    "/verify/queue",
    response_model=VerificationQueue,
    response_model_by_alias=True,
)
async def admin_verify_queue(
    _: AdminEmail,
    db: AsyncSession = Depends(get_db),
) -> VerificationQueue:
    now = datetime.now(timezone.utc)
    # Skip already-verified and rejected users — the queue is only for
    # people the admin still needs to act on.
    users = list(
        await db.scalars(
            select(User).where(
                User.deleted_at.is_(None),
                User.status.in_((UserStatus.signed_up, UserStatus.profile_complete)),
            )
        )
    )
    profiles_map = {p.user_id: p for p in await db.scalars(select(Profile))}
    business_map = {
        b.user_id: b for b in await db.scalars(select(BusinessProfile))
    }
    identities_by_user: dict[uuid.UUID, list[str]] = defaultdict(list)
    for ident in await db.scalars(select(Identity)):
        identities_by_user[ident.user_id].append(ident.value)

    groups: dict[str, list[QueueRow]] = {
        "signed_up": [],
        "primary_pending": [],
        "business_pending": [],
        "bank_pending": [],
    }
    for u in users:
        stage = _stage(profiles_map.get(u.id), business_map.get(u.id))
        if stage not in groups:
            continue
        p = profiles_map.get(u.id)
        bp = business_map.get(u.id)
        idents = identities_by_user.get(u.id, [])
        mobile = next((v for v in idents if v.isdigit()), None)
        # Guard against clock skew or unset updated_at. SQLite drops the
        # tz info round-trip, so normalize to naive for the subtraction.
        updated = u.updated_at or u.created_at
        updated_naive = updated.replace(tzinfo=None) if updated.tzinfo else updated
        now_naive = now.replace(tzinfo=None)
        dwell = max(0, (now_naive - updated_naive).days)
        groups[stage].append(
            QueueRow(
                user_id=str(u.id),
                full_name=p.full_name if p else None,
                mobile=mobile,
                company_name=bp.company_name if bp else None,
                state=p.state if p else None,
                dwell_days=dwell,
                updated_at=updated,
            )
        )
    # Sort each group by biggest dwell first — that's where admin should look.
    for k in groups:
        groups[k].sort(key=lambda r: r.dwell_days, reverse=True)
    return VerificationQueue(**groups)
