"""GET-JSON with timeout + retry for the HTTP providers."""
from __future__ import annotations

import httpx

from app.integrations._retry import TransientError, retry_async
from app.integrations.fx.base import FxError


async def get_json(
    url: str,
    *,
    params: dict | None = None,
    timeout: float,
    attempts: int,
    label: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> object:
    async def _once() -> object:
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=True) as client:
                resp = await client.get(url, params=params, headers={"accept": "application/json"})
        except httpx.HTTPError as e:
            raise TransientError(f"{label} unreachable: {e}") from e
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"{label} returned {resp.status_code}")
        if resp.status_code >= 300:
            raise FxError(f"{label} returned {resp.status_code}")
        try:
            return resp.json()
        except ValueError as e:
            raise FxError(f"{label} returned invalid JSON") from e

    try:
        return await retry_async(_once, attempts=attempts, label=label)
    except TransientError as e:
        raise FxError(str(e)) from e
