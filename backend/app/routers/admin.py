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
from pydantic import BaseModel, Field
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
from app.models.bank_details import BankDetails
from app.models.buyer import Buyer
from app.models.identity import Identity
from app.models.seller import Seller
from app.models.user import User, UserStatus, UserType
from app.schemas.base import CamelModel

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
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=settings.admin_session_max_age_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # flip to True once we're on HTTPS
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
    # Buyer/seller identities include phone + email. Prefer the numeric one.
    rows = await db.scalars(
        select(Identity.value).where(Identity.user_id == user_id)
    )
    vals = list(rows)
    for v in vals:
        if v and v.isdigit():
            return v
    return vals[0] if vals else None


def _stage(buyer: Buyer | None, seller: Seller | None, bank: BankDetails | None) -> str:
    """Bucket a user into the verification funnel."""
    primary = bool(
        buyer
        and buyer.full_name
        and buyer.email
        and buyer.address_line
        and buyer.city
        and buyer.state
        and buyer.pincode
    )
    business = bool(seller and seller.pan and seller.company_name)
    bank_ok = bool(bank and bank.account_number and bank.ifsc and bank.holder_name)
    if primary and business and bank_ok:
        return "verified"
    if primary and business:
        return "bank_pending"
    if primary:
        return "business_pending"
    if buyer and buyer.full_name:
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
    total_buyers = await db.scalar(
        select(func.count(User.id)).where(User.user_type == UserType.buyer)
    ) or 0
    total_sellers = await db.scalar(
        select(func.count(User.id)).where(User.user_type == UserType.seller)
    ) or 0
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

    # Funnel — pull all users + their relations in one pass. Fine for MVP scale.
    users = list(await db.scalars(select(User)))
    buyers_map = {b.user_id: b for b in await db.scalars(select(Buyer))}
    sellers_map = {s.user_id: s for s in await db.scalars(select(Seller))}
    banks_map = {b.user_id: b for b in await db.scalars(select(BankDetails))}
    funnel_counter: Counter[str] = Counter()
    for u in users:
        funnel_counter[_stage(buyers_map.get(u.id), sellers_map.get(u.id), banks_map.get(u.id))] += 1
    funnel = {
        "signed_up": funnel_counter.get("signed_up", 0),
        "primary_pending": funnel_counter.get("primary_pending", 0),
        "business_pending": funnel_counter.get("business_pending", 0),
        "bank_pending": funnel_counter.get("bank_pending", 0),
        "verified": funnel_counter.get("verified", 0),
    }

    # Top states — buyers vs sellers (join user_type via users_map)
    users_map = {u.id: u for u in users}
    state_buckets: dict[str, Counter[str]] = {"buyer": Counter(), "seller": Counter()}
    for b in buyers_map.values():
        if not b.state:
            continue
        u = users_map.get(b.user_id)
        if not u:
            continue
        state_buckets[u.user_type.value][b.state.strip().title()] += 1
    top_states = {
        role: [
            {"state": s, "count": c}
            for s, c in bucket.most_common(5)
        ]
        for role, bucket in state_buckets.items()
    }

    # Duplicate GSTIN / PAN alerts — render each duplicated user with their
    # display name if we have one; otherwise fall back to their mobile.
    async def _label(uid: uuid.UUID) -> str:
        b = buyers_map.get(uid)
        if b and b.full_name:
            return b.full_name
        mobile = await _primary_mobile(db, uid)
        return mobile or str(uid)[:8]

    def _people(ids: list[uuid.UUID]) -> list[dict[str, str]]:
        # Preserve encounter order; drop duplicates preserving first-seen.
        seen: set[uuid.UUID] = set()
        return [
            {"user_id": str(i)}  # label attached synchronously below
            for i in ids
            if not (i in seen or seen.add(i))
        ]

    gstin_map: dict[str, list[uuid.UUID]] = defaultdict(list)
    pan_map: dict[str, list[uuid.UUID]] = defaultdict(list)
    for s in sellers_map.values():
        if s.gstin:
            gstin_map[s.gstin.strip().upper()].append(s.user_id)
        if s.pan:
            pan_map[s.pan.strip().upper()].append(s.user_id)
    duplicate_alerts: list[dict[str, Any]] = []
    for gstin, ids in gstin_map.items():
        if len(ids) > 1:
            people = _people(ids)
            for p in people:
                p["label"] = await _label(uuid.UUID(p["user_id"]))
            duplicate_alerts.append({"kind": "GSTIN", "value": gstin, "users": people})
    for pan, ids in pan_map.items():
        if len(ids) > 1:
            people = _people(ids)
            for p in people:
                p["label"] = await _label(uuid.UUID(p["user_id"]))
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
    # Pre-seed every day so the chart shows zero-bars for empty days.
    buckets: dict[str, dict[str, int]] = {}
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[d] = {"buyer": 0, "seller": 0}
    for u in users:
        key = u.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if key in buckets:
            buckets[key][u.user_type.value] += 1
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
    result: list[RecentSignup] = []
    for u in users:
        buyer = await db.scalar(select(Buyer).where(Buyer.user_id == u.id))
        mobile = await _primary_mobile(db, u.id)
        result.append(
            RecentSignup(
                user_id=str(u.id),
                full_name=buyer.full_name if buyer else None,
                user_type=u.user_type.value,
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
    if user_type in {"buyer", "seller"}:
        stmt = stmt.where(User.user_type == UserType(user_type))
    if status in {s.value for s in UserStatus}:
        stmt = stmt.where(User.status == UserStatus(status))

    # Search: name / email / mobile / GSTIN / PAN. Do it in Python for MVP —
    # we're at hundreds of users. Move to indexed columns when we hit 10k+.
    all_users = list(await db.scalars(stmt.order_by(User.created_at.desc())))
    buyers_map = {b.user_id: b for b in await db.scalars(select(Buyer))}
    sellers_map = {s.user_id: s for s in await db.scalars(select(Seller))}
    banks_map = {b.user_id: b for b in await db.scalars(select(BankDetails))}
    identities_by_user: dict[uuid.UUID, list[str]] = defaultdict(list)
    for ident in await db.scalars(select(Identity)):
        identities_by_user[ident.user_id].append(ident.value)

    def matches_q(u: User) -> bool:
        if not q:
            return True
        needle = q.strip().lower()
        b = buyers_map.get(u.id)
        s = sellers_map.get(u.id)
        haystack: list[str] = []
        if b:
            if b.full_name:
                haystack.append(b.full_name)
            if b.email:
                haystack.append(b.email)
        if s:
            if s.gstin:
                haystack.append(s.gstin)
            if s.pan:
                haystack.append(s.pan)
            if s.company_name:
                haystack.append(s.company_name)
        haystack.extend(identities_by_user.get(u.id, []))
        return any(needle in v.lower() for v in haystack)

    filtered = [u for u in all_users if matches_q(u)]
    total = len(filtered)
    page = filtered[offset : offset + limit]

    items: list[UserRow] = []
    for u in page:
        b = buyers_map.get(u.id)
        s = sellers_map.get(u.id)
        bank = banks_map.get(u.id)
        idents = identities_by_user.get(u.id, [])
        mobile = next((v for v in idents if v.isdigit()), None)
        items.append(
            UserRow(
                user_id=str(u.id),
                full_name=b.full_name if b else None,
                user_type=u.user_type.value,
                status=u.status.value,
                stage=_stage(b, s, bank),
                mobile=mobile,
                email=(b.email if b else None),
                state=b.state if b else None,
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
    buyer = await db.scalar(select(Buyer).where(Buyer.user_id == uid))
    seller = await db.scalar(select(Seller).where(Seller.user_id == uid))
    bank = await db.scalar(select(BankDetails).where(BankDetails.user_id == uid))
    mobile = await _primary_mobile(db, uid)

    buyer_block: dict[str, Any] | None = None
    if buyer:
        buyer_block = {
            "fullName": buyer.full_name,
            "email": buyer.email,
            "addressLine": buyer.address_line,
            "city": buyer.city,
            "state": buyer.state,
            "pincode": buyer.pincode,
            "altMobile": buyer.alt_mobile,
            "altEmail": buyer.alt_email,
            "businessEmail": buyer.business_email,
            "websiteUrl": buyer.website_url,
        }
    seller_block: dict[str, Any] | None = None
    if seller:
        seller_block = {
            "gstin": seller.gstin,
            "pan": seller.pan,
            "companyName": seller.company_name,
            "udyam": seller.udyam,
            "aadhaar": seller.aadhaar,
            "tan": seller.tan,
        }
    bank_block: dict[str, Any] | None = None
    if bank:
        bank_block = {
            "accountNumber": bank.account_number,
            "ifsc": bank.ifsc,
            "holderName": bank.holder_name,
            "branchName": bank.branch_name,
            "bankName": bank.bank_name,
        }

    return UserDetail(
        user_id=str(user.id),
        user_type=user.user_type.value,
        status=user.status.value,
        stage=_stage(buyer, seller, bank),
        created_at=user.created_at,
        updated_at=user.updated_at,
        mobile=mobile,
        has_buyer_data=bool(buyer and buyer.full_name),
        has_seller_data=bool(seller),
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
    """Treat empty string in a PATCH body as an explicit clear."""
    if v is None:
        return None
    v = v.strip()
    return v or None


class AdminBuyerPatch(CamelModel):
    full_name: str | None = None
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    alt_mobile: str | None = None
    alt_email: str | None = None
    business_email: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class AdminSellerPatch(CamelModel):
    gstin: str | None = None
    pan: str | None = None
    company_name: str | None = None
    udyam: str | None = None
    aadhaar: str | None = None
    tan: str | None = None


class AdminBankPatch(CamelModel):
    account_number: str | None = None
    ifsc: str | None = None
    holder_name: str | None = None
    branch_name: str | None = None
    bank_name: str | None = None


class AdminUserPatch(CamelModel):
    buyer: AdminBuyerPatch | None = None
    seller: AdminSellerPatch | None = None
    bank: AdminBankPatch | None = None


def _apply_buyer_patch(buyer: Buyer, patch: AdminBuyerPatch) -> None:
    """Copy every field the admin sent onto the buyer row. Empty string clears
    a nullable field; None means 'don't touch this key'. full_name is required
    on the model, so we ignore attempts to blank it."""
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if field == "full_name":
            if cleaned:
                buyer.full_name = cleaned
            continue
        setattr(buyer, field, cleaned)


def _apply_seller_patch(seller: Seller, patch: AdminSellerPatch) -> None:
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if cleaned and field in {"pan", "gstin"}:
            cleaned = cleaned.upper()
        setattr(seller, field, cleaned)


def _apply_bank_patch(bank: BankDetails, patch: AdminBankPatch) -> None:
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        cleaned = _blank_to_none(value) if isinstance(value, str) else value
        if cleaned and field == "ifsc":
            cleaned = cleaned.upper()
        setattr(bank, field, cleaned)


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
        buyer = await db.scalar(select(Buyer).where(Buyer.user_id == uid))
        if buyer is None:
            name = _blank_to_none(payload.buyer.full_name)
            if not name:
                raise HTTPException(
                    status_code=400,
                    detail="Full name is required to create a buyer profile",
                )
            buyer = Buyer(user_id=uid, full_name=name)
            db.add(buyer)
        _apply_buyer_patch(buyer, payload.buyer)

    if payload.seller is not None:
        seller = await db.scalar(select(Seller).where(Seller.user_id == uid))
        if seller is None:
            seller = Seller(user_id=uid)
            db.add(seller)
        _apply_seller_patch(seller, payload.seller)

    if payload.bank is not None:
        bank = await db.scalar(select(BankDetails).where(BankDetails.user_id == uid))
        if bank is None:
            bank = BankDetails(user_id=uid)
            db.add(bank)
        _apply_bank_patch(bank, payload.bank)

    # Re-run the "all-three complete → verified" gate so admin edits keep the
    # user's status in sync with what the buyer/seller pages would compute.
    await db.flush()
    buyer2 = await db.scalar(select(Buyer).where(Buyer.user_id == uid))
    seller2 = await db.scalar(select(Seller).where(Seller.user_id == uid))
    bank2 = await db.scalar(select(BankDetails).where(BankDetails.user_id == uid))
    if _stage(buyer2, seller2, bank2) == "verified" and user.status != UserStatus.verified:
        user.status = UserStatus.verified

    await db.commit()
    return await _load_user_detail(db, uid)
