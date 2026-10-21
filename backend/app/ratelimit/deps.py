"""Process-wide limiter registry + FastAPI dependency helpers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request

from app.ratelimit.base import RateLimitRule
from app.ratelimit.limiter import RateLimiter
from app.ratelimit.memory import MemoryRateLimitBackend

_limiter: RateLimiter | None = None
_trusted_proxies = 0


def configure_limiter(limiter: RateLimiter, *, trusted_proxies: int = 0) -> None:
    global _limiter, _trusted_proxies
    _limiter = limiter
    _trusted_proxies = max(0, trusted_proxies)


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(MemoryRateLimitBackend())
    return _limiter


def client_ip(request: Request) -> str | None:
    """Best-effort client IP, safe against a spoofed ``X-Forwarded-For``.

    Each proxy *appends* the address it received the request from, so only
    the right-hand entries are trustworthy — the left-most one is whatever
    the client chose to send. With ``trusted_proxies = N`` (the number of
    proxies we run in front of the app) the client is the N-th entry from
    the right. With 0 the header is ignored and the socket peer is used.
    """
    if _trusted_proxies:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            hops = [h.strip() for h in xff.split(",") if h.strip()]
            if len(hops) >= _trusted_proxies:
                return hops[-_trusted_proxies]
            # Fewer entries than proxies: the request skipped part of the
            # chain, so nothing in the header can be trusted.
    return request.client.host if request.client else None


def ip_rate_limit(rule: RateLimitRule) -> Callable[[Request], Awaitable[None]]:
    """Dependency factory: ``Depends(ip_rate_limit(RULE))``."""

    async def _dep(request: Request) -> None:
        await get_limiter().check(rule, client_ip(request))

    _dep.__name__ = f"rate_limit_{rule.name.replace(':', '_')}"
    return _dep
