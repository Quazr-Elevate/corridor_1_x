"""Tiny async retry-with-backoff helper shared by integrations."""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

log = logging.getLogger("app.integrations.retry")


class TransientError(Exception):
    """Raise (or wrap) to signal that an operation may succeed if retried."""


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    retry_on: tuple[type[BaseException], ...] = (TransientError,),
    label: str = "operation",
) -> T:
    """Run ``fn`` up to ``attempts`` times, sleeping with exponential backoff
    + jitter between tries. Only exceptions in ``retry_on`` are retried."""
    attempts = max(1, attempts)
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except retry_on as e:
            if attempt >= attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay *= 0.5 + random.random() / 2
            log.warning("%s failed (attempt %d/%d): %s — retrying in %.2fs", label, attempt, attempts, e, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
