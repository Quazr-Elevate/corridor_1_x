"""Seed five test accounts spanning every business verification state.

Idempotent — rerunning resets each account so you can click through the
same flow again without manual DB fiddling.

Accounts (all password: ``TestPass123!``), one business each:

    1. verifyme1@test.com   — draft, 0/7 mandatory fields ("Start verification")
    2. verifyme2@test.com   — draft, 3/7 (name, position, phone)
    3. verifyme3@test.com   — draft, 7/7, not yet sent ("Ready to submit")
    4. verifyme4@test.com   — pending_verification (sitting in the admin queue)
    5. verifyme5@test.com   — rejected (with a reason, triggers the popup)

Run (from anywhere)::

    backend/.venv/bin/python backend/scripts/seed_test_users.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.business import Business, BusinessStatus  # noqa: E402
from app.models.user import AccountStatus, User, UserRole  # noqa: E402

PASSWORD = "TestPass123!"
NOW = datetime.now(tz=timezone.utc)

# email, full_name, position, phone, business fields, status, submitted, reason
_SEED: list[dict] = [
    dict(email="verifyme1@test.com", full_name="User One", position=None, phone=None,
         business=dict(legal_name=None, industry=None, operating_countries=None, trade_position=None),
         status=BusinessStatus.draft),
    dict(email="verifyme2@test.com", full_name="User Two", position="Sales Manager", phone="+91 9876500002",
         business=dict(legal_name=None, industry=None, operating_countries=None, trade_position=None),
         status=BusinessStatus.draft),
    dict(email="verifyme3@test.com", full_name="User Three", position="Export Manager", phone="+91 9876500003",
         business=dict(legal_name="Ready Co Private Limited", industry="Agri commodities · rice / grains",
                       operating_countries=["IN", "SA", "AE"], trade_position="seller"),
         status=BusinessStatus.draft),
    dict(email="verifyme4@test.com", full_name="User Four", position="Director", phone="+91 9876500004",
         business=dict(legal_name="Pending Co Private Limited", industry="Agri commodities · spices / condiments",
                       operating_countries=["IN", "QA"], trade_position="both"),
         status=BusinessStatus.pending_verification, submitted=NOW - timedelta(hours=3)),
    dict(email="verifyme5@test.com", full_name="User Five", position="Founder", phone="+91 9876500005",
         business=dict(legal_name="Rejected Co Private Limited", industry="Agri commodities · pulses / lentils",
                       operating_countries=["IN", "AE"], trade_position="buyer"),
         status=BusinessStatus.rejected, submitted=NOW - timedelta(days=2),
         reason=("Legal company name on your profile doesn't match the domain of your work email. "
                 "Please update to the registered business name and resubmit.")),
]


async def _upsert(db, row: dict) -> None:
    user = await db.scalar(select(User).where(User.email == row["email"]))
    if user is None:
        business = Business(country="IN")
        user = User(business=business, email=row["email"], role=UserRole.owner)
        db.add_all([business, user])
    business = user.business
    user.password_hash = hash_password(PASSWORD)
    user.account_status = AccountStatus.active
    user.email_verified_at = NOW - timedelta(days=1)
    user.full_name = row["full_name"]
    user.position = row["position"]
    user.phone = row["phone"]
    user.consent_at = user.consent_at or NOW - timedelta(days=1)
    user.consent_version = user.consent_version or "2026-08-29"
    user.deleted_at = None
    for key, value in row["business"].items():
        setattr(business, key, value)
    business.country = "IN"
    business.deleted_at = None
    business.verification_status = row["status"]
    business.verification_submitted_at = row.get("submitted")
    business.verified_at = None
    business.verification_rejected_reason = row.get("reason")
    await db.flush()


async def main() -> None:
    async with SessionLocal() as db:
        for row in _SEED:
            await _upsert(db, row)
        await db.commit()
    print(f"Seeded {len(_SEED)} test accounts (password: {PASSWORD})\n")
    print("  verifyme1@test.com  — draft, 0/7 fields")
    print("  verifyme2@test.com  — draft, 3/7 fields")
    print("  verifyme3@test.com  — draft, 7/7 (ready to submit)")
    print("  verifyme4@test.com  — pending_verification (in admin queue)")
    print("  verifyme5@test.com  — rejected (popup + resubmit)")


if __name__ == "__main__":
    asyncio.run(main())
