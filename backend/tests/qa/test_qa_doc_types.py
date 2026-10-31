"""QA-200 — Admin manages the per-country document list (FLOW-200, adapted).

Pegan's ``/admin/doc-requirements`` (country_code, slug, display_name,
help_url) maps to main's ``/admin/kyb/document-types`` (country, code, name,
input kind, format pattern, help text). Adapted: codes are lower-cased
rather than refused for capitals; ``help_url`` doesn't exist, so the
equivalent guards are tested (Aadhaar refused, invalid format pattern
refused); hidden types stay in the admin list and leave the trader dropdown.
"""
from __future__ import annotations

import pytest
from conftest import signup_and_login
from qa_helpers import uniq, uniq_code


def _body(**over) -> dict:
    return {"country": "IN", "code": uniq_code("qa200"), "name": "QA 200 test doc", "inputKind": "file", "isMandatory": True} | over


# QA-200.1 — non-admin can't access
async def test_requires_admin_cookie(client):
    assert (await client.get("/admin/kyb/document-types")).status_code == 401
    await signup_and_login(client, f"{uniq('qa200')}@test.cor1x.co")
    assert (await client.get("/admin/kyb/document-types")).status_code == 401
    assert (await client.post("/admin/kyb/document-types", json=_body())).status_code == 401


# QA-200.2 — create, list by country, edit, hide
async def test_full_lifecycle(client, admin_client):
    body = _body(helpText="A description")
    r = await admin_client.post("/admin/kyb/document-types", json=body)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["code"] == body["code"] and row["country"] == "IN"
    assert row["isMandatory"] is True and row["active"] is True

    assert body["code"] in {x["code"] for x in (await admin_client.get("/admin/kyb/document-types?country=IN")).json()}

    r = await admin_client.patch(
        f"/admin/kyb/document-types/{row['id']}", json={"name": "Renamed", "isMandatory": False, "helpText": "See the portal"}
    )
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched["name"] == "Renamed" and patched["isMandatory"] is False and patched["helpText"] == "See the portal"

    r = await admin_client.patch(f"/admin/kyb/document-types/{row['id']}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False
    # Hidden: still listed for admins, gone from the trader dropdown.
    assert body["code"] in {x["code"] for x in (await admin_client.get("/admin/kyb/document-types?country=IN")).json()}
    await signup_and_login(client, f"{uniq('qa200')}@test.cor1x.co")
    assert body["code"] not in {t["code"] for t in (await client.get("/kyb/document-types")).json()}


# QA-200.3 — code format refused (capitals are lower-cased, not refused)
@pytest.mark.parametrize("bad_code", ["has space", "-leading", "1digitfirst", "a" * 41, "trailing!"])
async def test_code_format_rejected(admin_client, bad_code):
    r = await admin_client.post("/admin/kyb/document-types", json=_body(code=bad_code))
    assert r.status_code == 422, r.text


async def test_code_upper_case_is_lowercased(admin_client):
    r = await admin_client.post("/admin/kyb/document-types", json=_body(code="QA_UPPER_DOC"))
    assert r.status_code == 201 and r.json()["code"] == "qa_upper_doc"


# QA-200.4 — unknown country code
async def test_unknown_country_rejected(admin_client):
    r = await admin_client.post("/admin/kyb/document-types", json=_body(country="XX"))
    assert r.status_code == 422 and "Unknown country code" in r.text


# QA-200.5 (main) — guards: no Aadhaar, valid format pattern
@pytest.mark.parametrize(
    "over",
    [{"code": "aadhaar"}, {"name": "Aadhar card"}, {"inputKind": "value", "valuePattern": "[unclosed"}],
)
async def test_unsafe_definitions_rejected(admin_client, over):
    assert (await admin_client.post("/admin/kyb/document-types", json=_body(**over))).status_code == 422


# QA-200.6 — duplicate (country, code) → 409
async def test_duplicate_conflict(admin_client):
    body = _body()
    assert (await admin_client.post("/admin/kyb/document-types", json=body)).status_code == 201
    assert (await admin_client.post("/admin/kyb/document-types", json=body)).status_code == 409


# QA-200.7 — country / code immutable on PATCH (extra keys ignored)
async def test_country_and_code_immutable_on_patch(admin_client):
    body = _body(isMandatory=False)
    row = (await admin_client.post("/admin/kyb/document-types", json=body)).json()
    r = await admin_client.patch(
        f"/admin/kyb/document-types/{row['id']}", json={"country": "AE", "code": "renamed_code", "name": "post-patch"}
    )
    assert r.status_code == 200
    patched = r.json()
    assert patched["country"] == "IN" and patched["code"] == body["code"] and patched["name"] == "post-patch"


# QA-200.8 — name min length
async def test_name_too_short(admin_client):
    r = await admin_client.post("/admin/kyb/document-types", json=_body(name=""))
    assert r.status_code == 422
