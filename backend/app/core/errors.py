"""Domain exceptions + the central handlers that map them to HTTP.

Services raise these (no FastAPI imports needed there); the handlers
registered in :func:`register_exception_handlers` turn them into the
``{"detail": "..."}`` shape the frontend already reads.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ratelimit import RateLimitExceeded

log = logging.getLogger("app.errors")


class DomainError(Exception):
    status_code: int = 400

    def __init__(self, detail: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers


class BadRequest(DomainError):
    status_code = 400


class Unauthorized(DomainError):
    status_code = 401


class Forbidden(DomainError):
    status_code = 403


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Locked(DomainError):
    """Account locked after repeated failed sign-ins."""

    status_code = 423


class PayloadTooLarge(DomainError):
    status_code = 413


class UnsupportedMediaType(DomainError):
    status_code = 415


class TooManyRequests(DomainError):
    status_code = 429

    def __init__(self, detail: str, *, retry_after: int) -> None:
        super().__init__(detail, headers={"Retry-After": str(max(1, int(retry_after)))})
        self.retry_after = retry_after


class UpstreamError(DomainError):
    """A third-party dependency (mail, lookups, …) failed."""

    status_code = 502


class ServiceUnavailable(DomainError):
    status_code = 503


def _fmt_retry(seconds: int) -> str:
    seconds = max(1, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        if exc.status_code >= 500:
            log.warning("domain_error status=%s detail=%r", exc.status_code, exc.detail)
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        log.info("rate_limited rule=%s retry_after=%s", exc.rule, exc.retry_after)
        return JSONResponse(
            {"detail": f"Too many attempts. Try again in {_fmt_retry(exc.retry_after)}."},
            status_code=429,
            headers={"Retry-After": str(max(1, int(exc.retry_after)))},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error type=%s", type(exc).__name__)
        return JSONResponse({"detail": "Internal server error."}, status_code=500)
