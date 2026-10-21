"""High-level limiter: rules + identifiers → allow / raise."""
from __future__ import annotations

from app.ratelimit.base import (
    RateLimitBackend,
    RateLimitExceeded,
    RateLimitResult,
    RateLimitRule,
)


class RateLimiter:
    """Applies :class:`RateLimitRule` budgets on top of a backend.

    ``multiplier`` scales every limit (e.g. 10x in dev) without turning the
    limiter off; ``enabled=False`` disables enforcement entirely.
    """

    def __init__(self, backend: RateLimitBackend, *, multiplier: int = 1, enabled: bool = True) -> None:
        self.backend = backend
        self.multiplier = max(1, int(multiplier))
        self.enabled = enabled

    def _key(self, rule: RateLimitRule, identifier: str) -> str:
        return f"{rule.name}:{identifier.strip().lower()}"

    async def hit(self, rule: RateLimitRule, identifier: str) -> RateLimitResult:
        limit = rule.limit * self.multiplier
        if not self.enabled:
            return RateLimitResult(True, limit, limit, 0)
        return await self.backend.hit(self._key(rule, identifier), limit, rule.window_sec)

    async def check(self, rule: RateLimitRule, identifier: str | None) -> None:
        """Record a hit; raise :class:`RateLimitExceeded` when over budget.
        A missing identifier (e.g. unknown client IP) is not limited."""
        if not identifier:
            return
        result = await self.hit(rule, identifier)
        if not result.allowed:
            raise RateLimitExceeded(rule.name, result.retry_after)

    async def reset(self) -> None:
        await self.backend.reset()
