"""Reusable rate limiting.

    from app.ratelimit import RateLimitRule, get_limiter, ip_rate_limit

    LOGIN_PER_IP = RateLimitRule("login:ip", limit=30, window_sec=900)

    @router.post("/login", dependencies=[Depends(ip_rate_limit(LOGIN_PER_IP))])
    async def login(...):
        await get_limiter().check(LOGIN_PER_EMAIL, email)

Exceeding a budget raises :class:`RateLimitExceeded`; the app maps it to a
429 with ``Retry-After``.
"""
from app.ratelimit.base import (
    RateLimitBackend,
    RateLimitExceeded,
    RateLimitResult,
    RateLimitRule,
)
from app.ratelimit.deps import client_ip, configure_limiter, get_limiter, ip_rate_limit
from app.ratelimit.limiter import RateLimiter
from app.ratelimit.memory import MemoryRateLimitBackend

__all__ = [
    "MemoryRateLimitBackend",
    "RateLimitBackend",
    "RateLimitExceeded",
    "RateLimitResult",
    "RateLimitRule",
    "RateLimiter",
    "client_ip",
    "configure_limiter",
    "get_limiter",
    "ip_rate_limit",
]
