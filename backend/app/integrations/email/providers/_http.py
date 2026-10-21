"""Shared POST-with-retry used by the hosted (HTTP API) providers."""
from __future__ import annotations

import httpx

from app.integrations._retry import TransientError, retry_async
from app.integrations.email.base import EmailConfig, EmailDeliveryError


async def post_json(
    config: EmailConfig,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict,
    provider: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.Response:
    async def _once() -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=config.http_timeout_sec, transport=transport) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as e:
            raise TransientError(f"{provider} unreachable: {e}") from e
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"{provider} returned {resp.status_code}")
        if resp.status_code >= 300:
            raise EmailDeliveryError(f"{provider} returned {resp.status_code}: {resp.text[:400]}")
        return resp

    try:
        return await retry_async(
            _once, attempts=config.max_attempts, label=f"email:{provider}"
        )
    except TransientError as e:
        raise EmailDeliveryError(str(e)) from e
