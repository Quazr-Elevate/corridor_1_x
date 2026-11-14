"""The API contract every route shares: the version prefix, the error
shape, and where the docs are served."""
from __future__ import annotations

import pytest
from conftest import ROOT_URL

from app.core.config import settings
from app.main import docs_urls


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
async def test_api_docs_are_not_served_outside_debug(client, path):
    assert settings.debug is False
    r = await client.get(ROOT_URL + path)
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
    r = await client.delete(ROOT_URL + "/health")
    assert r.status_code == 405 and r.json()["code"] == "request.method_not_allowed"


async def test_rate_limit_error_has_a_code(client):
    from app.modules.auth.router import FORGOT_PER_IP

    for _ in range(FORGOT_PER_IP.limit):
        await client.post("/auth/password/forgot", json={"email": "nobody@kaverifoods.in"})
    r = await client.post("/auth/password/forgot", json={"email": "nobody@kaverifoods.in"})
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limit.exceeded" and isinstance(r.json()["detail"], str)


# ── Version prefix ───────────────────────────────────────────────────


async def test_routes_answer_under_v1_only(client):
    assert (await client.get(ROOT_URL + "/v1/public/products")).status_code == 200
    r = await client.get(ROOT_URL + "/public/products")
    assert r.status_code == 404 and r.json()["code"] == "resource.not_found"
    # An unversioned path must not reach a handler even with a session-free POST.
    assert (await client.post(ROOT_URL + "/auth/login", json={})).status_code == 404


async def test_health_stays_outside_the_prefix(client):
    assert (await client.get(ROOT_URL + "/health")).status_code == 200
    assert (await client.get(ROOT_URL + "/v1/health")).status_code == 404


def test_every_route_except_health_is_versioned():
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.main import app

    paths = {c.path for c in iter_route_contexts(app.routes) if isinstance(c.original_route, APIRoute)}
    assert len(paths) > 50
    assert {p for p in paths if not p.startswith("/v1/")} == {"/health"}


# ── Unknown request fields ───────────────────────────────────────────


async def test_unknown_request_field_is_refused(client):
    r = await client.post("/auth/login", json={"email": "a@kaverifoods.in", "password": "x" * 12, "role": "admin"})
    assert r.status_code == 422
    assert r.json() == {
        "detail": "role: This field is not accepted.",
        "code": "request.unknown_field",
        "fields": [{"field": "role", "message": "This field is not accepted."}],
    }


async def test_unknown_field_next_to_a_bad_value_is_a_validation_failure(client):
    r = await client.post("/auth/signup/code", json={"role": "admin"})
    assert r.status_code == 422 and r.json()["code"] == "validation.failed"
    assert {f["field"] for f in r.json()["fields"]} == {"email", "role"}


def test_every_json_request_body_is_strict():
    from fastapi.routing import APIRoute, iter_route_contexts
    from pydantic import BaseModel

    from app.main import app

    loose = []
    for ctx in iter_route_contexts(app.routes):
        if not isinstance(ctx.original_route, APIRoute):
            continue
        for param in ctx.dependant.body_params:
            model = param.field_info.annotation
            if isinstance(model, type) and issubclass(model, BaseModel) and model.model_config.get("extra") != "forbid":
                loose.append(f"{ctx.path}: {model.__name__}")
    assert not loose, "Request bodies that accept unknown fields:\n" + "\n".join(loose)
