"""Fetch today's USD exchange rates and recompute every listing's price_usd.

Same work as the in-process background task (FX_ENABLED) — use this from
cron / a Railway cron service when the API runs several workers or with
FX_ENABLED=false. Run (from anywhere)::

    backend/.venv/bin/python backend/scripts/refresh_rates.py

Providers come from FX_PROVIDERS (default "frankfurter,fawazahmed0"); AED
falls back to its peg; a rate that fails the sanity bounds keeps the last
stored one. Exit code 1 when no currency could be stored.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.main import configure_integrations  # noqa: E402
from app.models.exchange_rate import ExchangeRate  # noqa: E402
from app.modules.fx.service import refresh_rates  # noqa: E402


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    configure_integrations(settings)
    async with SessionLocal() as db:
        result = await refresh_rates(db)
        rows = list(
            await db.scalars(
                select(ExchangeRate).order_by(ExchangeRate.as_of.desc(), ExchangeRate.quote).limit(20)
            )
        )
    await engine.dispose()
    print(f"providers: {settings.fx_providers}")
    print(f"stored:    {', '.join(f'{q.quote}={q.rate} ({q.source}, {q.as_of})' for q in result.stored) or '-'}")
    print(f"rejected:  {', '.join(result.rejected) or '-'}   missing: {', '.join(result.missing) or '-'}")
    print(f"listings recomputed: {result.products_updated}")
    print("\nexchange_rates (latest 20):")
    print(f"  {'base':<5}{'quote':<6}{'rate':>14}  {'as_of':<11} {'source':<12} fetched_at")
    for r in rows:
        print(f"  {r.base:<5}{r.quote:<6}{r.rate:>14}  {r.as_of!s:<11} {r.source:<12} {r.fetched_at:%Y-%m-%d %H:%M:%S}Z")
    return 0 if result.stored else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
