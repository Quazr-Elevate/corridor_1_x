"""Security response headers (pure ASGI).

* ``X-Content-Type-Options: nosniff``, ``Referrer-Policy: no-referrer``,
  a locked-down ``Permissions-Policy``;
* ``Content-Security-Policy: frame-ancestors`` limited to the API itself and
  the frontend origins (the web app previews KYB PDFs in an iframe — this
  replaces ``X-Frame-Options``, which can't list several origins);
* ``Strict-Transport-Security`` when cookies are Secure (HTTPS deployments);
* ``Cache-Control: no-store`` on every response that didn't set its own,
  so personal data never lands in browser or proxy caches.
"""
from __future__ import annotations

from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, frame_ancestors: Iterable[str], hsts: bool) -> None:
        self.app = app
        ancestors = " ".join(dict.fromkeys(o.rstrip("/") for o in frame_ancestors if o))
        self.headers: list[tuple[bytes, bytes]] = [
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"no-referrer"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
            (b"content-security-policy", f"frame-ancestors 'self' {ancestors}".strip().encode("latin-1")),
            (b"cross-origin-opener-policy", b"same-origin"),
        ]
        if hsts:
            self.headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in self.headers if k not in present)
                if b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send)
