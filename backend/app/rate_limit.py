"""In-process rate limiter — trivial, dict-based, single-worker-safe.

Only used for /otp/send today. Swap for Redis when we go multi-worker
or need per-IP throttling. Interface stays the same either way.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

from app.config import settings

# {identifier: [unix_ts, unix_ts, ...]}
_events: dict[str, list[float]] = defaultdict(list)

WINDOW_SEC = 60 * 60  # 1 hour
MAX_SENDS_PER_WINDOW = 3


def check_otp_rate_limit(identifier: str) -> None:
    """Raise 429 if this identifier has burned through its OTP send quota.

    Debug mode (dev) relaxes the limit to 20/hour so testing doesn't wedge
    itself.
    """
    key = identifier.strip().lower()
    now = time.time()
    hits = _events[key]
    # Drop events outside the sliding window.
    _events[key] = [t for t in hits if now - t < WINDOW_SEC]
    limit = 20 if settings.debug else MAX_SENDS_PER_WINDOW
    if len(_events[key]) >= limit:
        oldest = min(_events[key])
        retry_in = int(WINDOW_SEC - (now - oldest))
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many OTP requests. Try again in {retry_in // 60}m "
                f"{retry_in % 60}s."
            ),
            headers={"Retry-After": str(retry_in)},
        )
    _events[key].append(now)
