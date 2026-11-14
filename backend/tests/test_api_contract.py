"""The API contract every route shares: where the docs are served."""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.main import docs_urls


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
async def test_api_docs_are_not_served_outside_debug(client, path):
    assert settings.debug is False
    r = await client.get(path)
    assert r.status_code == 404


def test_api_docs_are_served_in_debug():
    urls = docs_urls(settings.model_copy(update={"debug": True}))
    assert urls == {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}
    assert set(docs_urls(settings).values()) == {None}
