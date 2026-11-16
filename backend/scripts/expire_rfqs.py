"""Close RFQs whose open period ran out without an offer (cron, hourly).

The lists also run this when they are read, so a missed run only delays the
status change; it never lets an expired RFQ be worked.

    python scripts/expire_rfqs.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal  # noqa: E402
from app.modules.rfq.service import expire_due  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        closed = await expire_due(db)
    print(f"Expired {closed} request(s).")


if __name__ == "__main__":
    asyncio.run(main())
