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


# ── One error shape: {detail, code, fields?} ─────────────────────────


async def test_domain_error_has_a_string_detail_and_a_code(client):
    r = await client.get("/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not signed in", "code": "auth.required"}


async def test_validation_error_has_a_string_detail_a_code_and_fields(client):
    r = await client.post("/auth/signup/code", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation.failed"
    assert isinstance(body["detail"], str) and body["detail"].startswith("email: ")
    assert body["fields"] == [{"field": "email", "message": body["detail"].removeprefix("email: ")}]


async def test_unknown_path_and_wrong_method_use_the_same_shape(client):
    r = await client.get("/no-such-route")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found", "code": "resource.not_found"}
    r = await client.delete("/health")
    assert r.status_code == 405 and r.json()["code"] == "request.method_not_allowed"


async def test_rate_limit_error_has_a_code(client):
    from app.modules.auth.router import FORGOT_PER_IP

    for _ in range(FORGOT_PER_IP.limit):
        await client.post("/auth/password/forgot", json={"email": "nobody@kaverifoods.in"})
    r = await client.post("/auth/password/forgot", json={"email": "nobody@kaverifoods.in"})
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limit.exceeded" and isinstance(r.json()["detail"], str)
