"""Cross-site request forgery (CSRF) guard — an Origin check.

Why: in production the session cookie is ``SameSite=None`` (frontend and API
on different sites), so the browser attaches it even to requests started by
*another* website. A malicious page could submit a hidden form to a
state-changing endpoint (e.g. ``POST /products/{id}/contact-reveal``) and the
victim's cookie would ride along.

How: browsers always send an ``Origin`` header on cross-site (and modern
same-site) POST/PUT/PATCH/DELETE requests, and a page cannot forge it. For
those methods we require the Origin — or, if a browser omitted it, the
Referer's origin — to be one of our own frontend origins. Requests carrying
neither header are not from a browser page (curl, server-to-server, tests)
and can't carry a victim's cookie, so they pass.

Safe methods (GET/HEAD/OPTIONS) are never blocked; they must not change
state anyway.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

log = logging.getLogger("app.csrf")

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LOCALHOST = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def _origin_of(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


class CSRFOriginMiddleware:
    """Reject unsafe-method requests whose Origin/Referer is not ours."""

    def __init__(self, app: ASGIApp, *, trusted_origins: list[str], allow_localhost: bool) -> None:
        self.app = app
        self.trusted = {o.rstrip("/").lower() for o in trusted_origins if o}
        self.allow_localhost = allow_localhost

    def _trusted(self, origin: str) -> bool:
        return origin in self.trusted or (self.allow_localhost and bool(_LOCALHOST.match(origin)))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        origin = headers.get("origin")
        if origin is not None:
            # "null" (sandboxed iframes, file://, some redirects) is never ours.
            source = origin.rstrip("/").lower() if origin != "null" else None
        else:
            referer = headers.get("referer")
            source = _origin_of(referer) if referer else ""  # "" = no browser headers

        if source == "" or (source and self._trusted(source)):
            await self.app(scope, receive, send)
            return

        log.warning("csrf_blocked method=%s path=%s origin=%s", scope["method"], scope["path"], origin or headers.get("referer"))
        body = json.dumps({"detail": "Cross-site request blocked."}).encode()
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
