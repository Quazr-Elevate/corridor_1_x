"""In-process sliding-window-log backend.

Exact (no bucket approximation), O(hits-in-window) memory per key. Fine for
a single uvicorn worker; use a shared backend (Redis) once there are
several workers/replicas, otherwise each process enforces its own budget.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from app.ratelimit.base import RateLimitBackend, RateLimitResult


class MemoryRateLimitBackend(RateLimitBackend):
    def __init__(self, *, clock: Callable[[], float] = time.monotonic, max_keys: int = 100_000) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    async def hit(self, key: str, limit: int, window_sec: int) -> RateLimitResult:
        now = self._clock()
        cutoff = now - window_sec
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                if len(self._hits) >= self._max_keys:
                    self._sweep(cutoff)
                q = self._hits[key] = deque()
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry = max(1, math.ceil(q[0] + window_sec - now))
                return RateLimitResult(False, limit, 0, retry)
            q.append(now)
            return RateLimitResult(True, limit, limit - len(q), 0)

    async def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

    def _sweep(self, cutoff: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]:
            del self._hits[k]
