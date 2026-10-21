"""In-process daily rate refresh (started from the FastAPI lifespan when
``FX_ENABLED``).

Runs on start when today's rates are missing, then every
``FX_REFRESH_HOURS``; a failed run retries after ``RETRY_SECONDS``. It is a
plain asyncio task — it never blocks requests and is cancelled on shutdown.
Each API process runs its own copy (harmless: the refresh is an idempotent
upsert), so with several workers prefer FX_ENABLED=false + the cron script
``scripts/refresh_rates.py``.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from app.core.db import SessionLocal
from app.modules.fx.service import refresh_due, refresh_rates

log = logging.getLogger("app.fx")

RETRY_SECONDS = 15 * 60


class FxRefresher:
    def __init__(self, interval_hours: float) -> None:
        self.interval = max(60.0, interval_hours * 3600)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="fx-refresh")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        first = True
        while True:
            delay = self.interval
            try:
                async with SessionLocal() as db:
                    if not first or await refresh_due(db):
                        await refresh_rates(db)
                    else:
                        log.info("fx: today's rates already stored — next refresh in %.0fh", self.interval / 3600)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("fx: refresh failed — retrying in %ds", RETRY_SECONDS)
                delay = min(RETRY_SECONDS, self.interval)
            first = False
            await asyncio.sleep(delay)
