"""Structured logging + request-id middleware.

* :func:`configure_logging` installs one stdout handler on the root logger
  using either a ``key=value`` or JSON formatter (``LOG_FORMAT``).
* :class:`RequestContextMiddleware` (pure ASGI) assigns every request an id
  (reusing an inbound ``X-Request-ID`` when sane), exposes it through a
  contextvar so every log line carries it, echoes it in the response
  header, and emits one access line per request — including the signed-in
  actor (``user:<id>`` / ``admin:<id>``, set via :func:`set_actor`), never
  the IP or body.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
# A mutable holder (not the value) so auth dependencies running in a copied
# context can still fill it in for the access line.
_actor_var: ContextVar[dict[str, str] | None] = ContextVar("actor", default=None)


def set_actor(kind: str, actor_id: object) -> None:
    """Record who made the current request (``user`` / ``admin`` + id)."""
    holder = _actor_var.get()
    if holder is not None:
        holder["actor"] = f"{kind}:{actor_id}"

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_STD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

access_log = logging.getLogger("app.access")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def _extras(record: logging.LogRecord) -> dict:
    return {
        k: v
        for k, v in record.__dict__.items()
        if k not in _STD_ATTRS and k != "request_id" and not k.startswith("_")
    }


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        parts = [
            f"ts={ts}",
            f"level={record.levelname}",
            f"logger={record.name}",
            f"request_id={getattr(record, 'request_id', '-')}",
            f"msg={json.dumps(record.getMessage(), ensure_ascii=False)}",
        ]
        for k, v in _extras(record).items():
            parts.append(f"{k}={json.dumps(v, default=str, ensure_ascii=False)}")
        line = " ".join(parts)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


_configured = False


def configure_logging(level: str = "INFO", fmt: str = "kv") -> None:
    """Idempotent — safe to call on every app factory invocation."""
    global _configured
    root = logging.getLogger()
    root.setLevel(level.upper())
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt.lower() == "json" else KeyValueFormatter())
    handler.addFilter(_RequestIdFilter())
    handler.set_name("cor1x")
    root.addHandler(handler)
    # Uvicorn's own access log duplicates ours; keep its error log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _configured = True


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                inbound = value.decode("latin-1")
                break
        rid = inbound if inbound and _REQUEST_ID_RE.match(inbound) else uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        actor = {"actor": "-"}
        _actor_var.set(actor)

        start = time.perf_counter()
        status_holder = {"status": 500}

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            ms = round((time.perf_counter() - start) * 1000, 1)
            path = scope.get("path", "")
            if path != "/health":
                access_log.info(
                    "request",
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status": status_holder["status"],
                        "duration_ms": ms,
                        "actor": actor["actor"],
                    },
                )
