"""Seed five test users spanning every verification state.

Idempotent — rerunning the script resets each user's state so you can
click through the same flow again without manual DB fiddling.

Users (all password: ``TestPass123!``):

    1. verifyme1@test.com   — email_verified, PROFILE EMPTY
                               (fresh signup, "Start verification")
    2. verifyme2@test.com   — email_verified, 3/7 FIELDS FILLED
                               ("Almost there — 4 fields missing")
    3. verifyme3@test.com   — email_verified, ALL 7 FILLED, NOT YET SENT
                               ("Ready to submit")
    4. verifyme4@test.com   — pending_verification (sitting in admin queue)
    5. verifyme5@test.com   — rejected (with a reason, triggers popup)

Run from backend/::

    python -m scripts.seed_test_users
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models.business_profile import BusinessProfile
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.routers.auth import _hash_password


PASSWORD = "TestPass123!"

NOW = datetime.now(tz=timezone.utc)


async def _upsert_user(
    db,
    *,
    email: str,
    business_name: str,
    status: UserStatus,
    verification_submitted_at: datetime | None = None,
    verified_at: datetime | None = None,
    rejected_reason: str | None = None,
) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
    user.business_name = business_name
    user.password_hash = _hash_password(PASSWORD)
    user.email_verified_at = NOW - timedelta(days=1)
    user.status = status
    user.verification_submitted_at = verification_submitted_at
    user.verified_at = verified_at
    user.verification_rejected_reason = rejected_reason
    user.deleted_at = None
    await db.flush()
    return user


async def _write_profile(
    db,
    user: User,
    *,
    full_name: str,
    position: str | None,
    phone: str | None,
) -> None:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        profile = Profile(user_id=user.id, full_name=full_name)
        db.add(profile)
    profile.full_name = full_name
    profile.position = position
    profile.phone = phone
    profile.country = "India"


async def _write_business(
    db,
    user: User,
    *,
    legal_name: str | None,
    industry: str | None,
    operating_countries: list[str] | None,
    trade_position: str | None,
) -> None:
    biz = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    if biz is None:
        biz = BusinessProfile(user_id=user.id)
        db.add(biz)
    biz.legal_name = legal_name
    biz.industry = industry
    biz.operating_countries = operating_countries
    biz.trade_position = trade_position


async def main() -> None:
    async with SessionLocal() as db:
        # 1. Empty profile — "Start verification"
        u1 = await _upsert_user(
            db,
            email="verifyme1@test.com",
            business_name="Blank Co",
            status=UserStatus.email_verified,
        )
        await _write_profile(db, u1, full_name="User One", position=None, phone=None)
        await _write_business(
            db, u1,
            legal_name=None, industry=None,
            operating_countries=None, trade_position=None,
        )

        # 2. Partial — only Primary fields filled
        u2 = await _upsert_user(
            db,
            email="verifyme2@test.com",
            business_name="Partial Co",
            status=UserStatus.email_verified,
        )
        await _write_profile(
            db, u2,
            full_name="User Two", position="Sales Manager", phone="+91 9876500002",
        )
        await _write_business(
            db, u2,
            legal_name=None, industry=None,
            operating_countries=None, trade_position=None,
        )

        # 3. All 7 filled, not yet submitted — "Ready to submit"
        u3 = await _upsert_user(
            db,
            email="verifyme3@test.com",
            business_name="Ready Co",
            status=UserStatus.email_verified,
        )
        await _write_profile(
            db, u3,
            full_name="User Three", position="Export Manager",
            phone="+91 9876500003",
        )
        await _write_business(
            db, u3,
            legal_name="Ready Co Private Limited",
            industry="Agri commodities · rice / grains",
            operating_countries=["IND", "SAU", "ARE"],
            trade_position="seller",
        )

        # 4. Submitted, waiting on admin — "Under review"
        u4 = await _upsert_user(
            db,
            email="verifyme4@test.com",
            business_name="Pending Co",
            status=UserStatus.pending_verification,
            verification_submitted_at=NOW - timedelta(hours=3),
        )
        await _write_profile(
            db, u4,
            full_name="User Four", position="Director",
            phone="+91 9876500004",
        )
        await _write_business(
            db, u4,
            legal_name="Pending Co Private Limited",
            industry="Agri commodities · spices / condiments",
            operating_countries=["IND", "QAT"],
            trade_position="both",
        )

        # 5. Rejected — popup on login, bar reads "Resubmit"
        u5 = await _upsert_user(
            db,
            email="verifyme5@test.com",
            business_name="Rejected Co",
            status=UserStatus.rejected,
            verification_submitted_at=NOW - timedelta(days=2),
            rejected_reason=(
                "Legal company name on your profile doesn't match the "
                "domain of your work email. Please update to the registered "
                "business name and resubmit."
            ),
        )
        await _write_profile(
            db, u5,
            full_name="User Five", position="Founder",
            phone="+91 9876500005",
        )
        await _write_business(
            db, u5,
            legal_name="Rejected Co Private Limited",
            industry="Agri commodities · pulses / lentils",
            operating_countries=["IND", "ARE"],
            trade_position="buyer",
        )

        await db.commit()
        print("Seeded 5 test users (password: TestPass123!)\n")
        print("  verifyme1@test.com  — email_verified, 0/7 fields")
        print("  verifyme2@test.com  — email_verified, 3/7 fields")
        print("  verifyme3@test.com  — email_verified, 7/7 (ready to submit)")
        print("  verifyme4@test.com  — pending_verification (in admin queue)")
        print("  verifyme5@test.com  — rejected (popup + resubmit)")


if __name__ == "__main__":
    asyncio.run(main())
