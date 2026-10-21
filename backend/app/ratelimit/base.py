"""Rate-limit primitives — app-agnostic.

A :class:`RateLimitRule` says "at most ``limit`` hits per ``window_sec``".
A :class:`RateLimitBackend` stores hits per key and answers whether one
more is allowed. Backends: in-memory sliding window (single process) now;
a Redis backend (sorted-set sliding window) can implement the same
interface for multi-worker deployments.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_sec: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until the next hit would be allowed (0 if allowed)


class RateLimitExceeded(Exception):
    def __init__(self, rule: str, retry_after: int) -> None:
        super().__init__(f"rate limit exceeded: {rule} (retry in {retry_after}s)")
        self.rule = rule
        self.retry_after = retry_after


class RateLimitBackend(ABC):
    @abstractmethod
    async def hit(self, key: str, limit: int, window_sec: int) -> RateLimitResult:
        """Record one hit for ``key`` if allowed; never records a denied hit."""

    @abstractmethod
    async def reset(self, key: str | None = None) -> None:
        """Forget ``key`` (or everything when ``None``)."""
