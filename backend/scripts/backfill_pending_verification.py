"""One-shot backfill: promote eligible users into pending_verification.

Before ``maybe_submit_for_verification`` was fixed to accept the
``email_verified`` state, a user who filled all seven mandatory fields
still sat at ``email_verified`` because the auto-flip only ran from
``active`` — which the signup flow never actually sets. This script
walks every user that is eligible for review (email verified, has a
profile + business row, all seven fields filled, not already in
pending/verified) and promotes them so the admin queue reflects reality.

Idempotent — rerunnable safely.

Run from backend/::

    python -m scripts.backfill_pending_verification
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models.business_profile import BusinessProfile
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.verification import maybe_submit_for_verification


async def main() -> None:
    async with SessionLocal() as db:
        users = list(
            await db.scalars(
                select(User).where(
                    User.deleted_at.is_(None),
                    User.status.in_(
                        (UserStatus.email_verified, UserStatus.active, UserStatus.rejected)
                    ),
                )
            )
        )
        promoted = 0
        for user in users:
            profile = await db.scalar(
                select(Profile).where(Profile.user_id == user.id)
            )
            business = await db.scalar(
                select(BusinessProfile).where(BusinessProfile.user_id == user.id)
            )
            if maybe_submit_for_verification(user, profile, business):
                promoted += 1
                print(f"  -> {user.email}: promoted to pending_verification")
        await db.commit()
        print(f"\nDone. {promoted} user(s) promoted; {len(users) - promoted} already up-to-date or incomplete.")


if __name__ == "__main__":
    asyncio.run(main())
