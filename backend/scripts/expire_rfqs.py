"""Close RFQs whose open period ran out without an offer, mark offers past
their date expired, and remind buyers of offers that end tomorrow (cron,
hourly: CX-178, CX-183).

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
from app.modules.accounts.service import get_owner  # noqa: E402
from app.modules.quotes.service import expire_offers_due, offers_to_remind  # noqa: E402
from app.modules.rfq.service import expire_due  # noqa: E402


async def main() -> None:
    configure_integrations(settings)  # the mail provider, as the API configures it
    async with SessionLocal() as db:
        closed = await expire_due(db)
        offers = await expire_offers_due(db)
        due = await offers_to_remind(db)
        owners = [(await get_owner(db, offer.buyer_business_id), offer, rfq) for offer, rfq in due]
        await db.commit()
    for owner, offer, rfq in owners:
        if owner is not None:
            await notifications.deliver_safely(
                notifications.send_offer_expiring, to=owner.email, first_name=notifications.first_name_of(owner.full_name),
                category=rfq.category, rfq_id=str(rfq.id), valid_until=offer.valid_until,
            )
    print(f"Expired {closed} request(s) and {offers} offer(s); reminded {len(owners)} buyer(s).")


if __name__ == "__main__":
    asyncio.run(main())
