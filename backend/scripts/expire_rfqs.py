"""Close RFQs whose open period ran out without an offer, mark offers past
their date expired, remind buyers of offers that end tomorrow, write off
plan credits whose plan has ended, and delete sign-up and reset codes older
than 24 hours (cron, hourly: CX-178, CX-183, CX-173, CX-149).

The lists also run this when they are read, so a missed run only delays the
status change; it never lets an expired RFQ be worked.

    python scripts/expire_rfqs.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import notifications  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.main import configure_integrations  # noqa: E402
from app.modules.accounts.service import owner_contact  # noqa: E402
from app.modules.auth.service import purge_old_codes  # noqa: E402
from app.modules.credits.service import expire_due_plans  # noqa: E402
from app.modules.quotes.service import expire_offers_due, offers_to_remind  # noqa: E402
from app.modules.rfq.service import expire_due  # noqa: E402


async def main() -> None:
    configure_integrations(settings)  # the mail provider, as the API configures it
    async with SessionLocal() as db:
        closed = await expire_due(db)
        offers = await expire_offers_due(db)
        plans = await expire_due_plans(db)
        due = await offers_to_remind(db)
        owners = [(await owner_contact(db, offer.buyer_business_id), offer, rfq) for offer, rfq in due]
        codes = await purge_old_codes(db)
        await db.commit()
    for owner, offer, rfq in owners:
        if owner is not None:
            await notifications.deliver_safely(
                notifications.send_offer_expiring, to=owner.email, first_name=notifications.first_name_of(owner.full_name),
                category=rfq.category, rfq_id=str(rfq.id), valid_until=offer.valid_until,
            )
    print(
        f"Expired {closed} request(s), {offers} offer(s) and the credits of {plans} plan(s); "
        f"reminded {len(owners)} buyer(s); deleted {codes} old email code(s)."
    )


if __name__ == "__main__":
    asyncio.run(main())
