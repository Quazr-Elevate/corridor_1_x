"""Domain exceptions + the central handlers that map them to HTTP.

Services raise these (no FastAPI imports needed there); the handlers
registered in :func:`register_exception_handlers` turn them into the one
error shape every route returns::

    {"detail": "<message for the user>", "code": "<stable identifier>",
     "fields": [{"field": "...", "message": "..."}]}   # validation only

``detail`` is always a string. Clients branch on ``code``, never on the
wording of ``detail``.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ratelimit import RateLimitExceeded

log = logging.getLogger("app.errors")


class DomainError(Exception):
    status_code: int = 400
    code: str = "request.invalid"

    def __init__(
        self, detail: str, *, code: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers
        if code is not None:
            self.code = code


class BadRequest(DomainError):
    status_code = 400
    code = "request.invalid"


class Unauthorized(DomainError):
    status_code = 401
    code = "auth.required"


class PaymentRequired(DomainError):
    """The company's credit balance does not cover the action."""

    status_code = 402
    code = "credits.insufficient"


class Forbidden(DomainError):
    status_code = 403
    code = "auth.forbidden"


class NotFound(DomainError):
    status_code = 404
    code = "resource.not_found"


class Conflict(DomainError):
    status_code = 409
    code = "resource.conflict"


class Locked(DomainError):
    """Account locked after repeated failed sign-ins."""

    status_code = 423
    code = "auth.locked"


class PayloadTooLarge(DomainError):
    status_code = 413
    code = "request.too_large"


class UnsupportedMediaType(DomainError):
    status_code = 415
    code = "request.unsupported_media_type"


class TooManyRequests(DomainError):
    status_code = 429
    code = "rate_limit.exceeded"

    def __init__(self, detail: str, *, retry_after: int) -> None:
        super().__init__(detail, headers={"Retry-After": str(max(1, int(retry_after)))})
        self.retry_after = retry_after


class UpstreamError(DomainError):
    """A third-party dependency (mail, lookups, …) failed."""

    status_code = 502
    code = "upstream.failed"


class ServiceUnavailable(DomainError):
    status_code = 503
    code = "service.unavailable"


VALIDATION_FAILED = "validation.failed"
UNKNOWN_FIELD = "request.unknown_field"

_HTTP_CODES = {404: "resource.not_found", 405: "request.method_not_allowed"}
# Where a value came from is not part of the field's name.
_LOC_PREFIXES = {"body", "query", "path", "header", "cookie"}
# Pydantic adds the union branch or validator chain it tried to the location
# ("function-after[...]", "str", "literal['']"); a person needs only the field.
_LOC_TAGS = {"str", "int", "float", "bool", "list", "dict", "none", "date", "datetime", "decimal"}


def _is_loc_tag(part: str) -> bool:
    return "[" in part or part.lower() in _LOC_TAGS


def error_body(detail: str, code: str, fields: list[dict[str, str]] | None = None) -> dict:
    body: dict = {"detail": detail, "code": code}
    if fields:
        body["fields"] = fields
    return body


def _is_unknown_field(err: dict) -> bool:
    return err.get("type") == "extra_forbidden"


def _validation_fields(exc: RequestValidationError) -> list[dict[str, str]]:
    fields = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        if loc and loc[0] in _LOC_PREFIXES:
            loc = loc[1:]
        loc = [part for part in loc if not _is_loc_tag(part)]
        if _is_unknown_field(err):
            message = "This field is not accepted."
        else:
            message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        fields.append({"field": ".".join(loc), "message": message})
    return fields


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
            error_body(exc.detail, exc.code), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = _validation_fields(exc)
        first = fields[0] if fields else {"field": "", "message": "The request is not valid."}
        detail = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
        # An unknown field is the caller's bug, not the user's input: its own code.
        unknown_only = bool(exc.errors()) and all(_is_unknown_field(e) for e in exc.errors())
        code = UNKNOWN_FIELD if unknown_only else VALIDATION_FAILED
        return JSONResponse(error_body(detail, code, fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by the framework itself: an unknown path, a wrong method.
        code = _HTTP_CODES.get(exc.status_code, f"http.{exc.status_code}")
        return JSONResponse(
            error_body(str(exc.detail), code), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        log.info("rate_limited rule=%s retry_after=%s", exc.rule, exc.retry_after)
        return JSONResponse(
            error_body(
                f"Too many attempts. Try again in {_fmt_retry(exc.retry_after)}.", TooManyRequests.code
            ),
            status_code=429,
            headers={"Retry-After": str(max(1, int(exc.retry_after)))},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error type=%s", type(exc).__name__)
        return JSONResponse(error_body("Internal server error.", "server.error"), status_code=500)
