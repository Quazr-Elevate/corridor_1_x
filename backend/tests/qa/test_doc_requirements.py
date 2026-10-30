"""QA-200 — Admin doc-requirements CRUD (FLOW-200)."""
from __future__ import annotations

import pytest

from tests.qa.conftest import uniq


# QA-200.1 — non-admin can't access
async def test_requires_admin_cookie(client):
    r = await client.get("/admin/doc-requirements")
    assert r.status_code == 401


# QA-200.2 — happy path: create, list filtered, patch, deactivate
async def test_full_lifecycle(admin_client):
    slug = uniq("qa200").replace("-", "_")
    # Create
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={
            "countryCode": "IN",
            "slug": slug,
            "displayName": "QA 200 test doc",
            "description": "A description",
            "isMandatory": True,
        },
    )
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["slug"] == slug and row["countryCode"] == "IN"
    assert row["isMandatory"] is True and row["isActive"] is True

    # List with country filter — our row is present
    r = await admin_client.get("/admin/doc-requirements?country=IN")
    assert r.status_code == 200
    slugs = {x["slug"] for x in r.json()}
    assert slug in slugs

    # PATCH mutable fields
    r = await admin_client.patch(
        f"/admin/doc-requirements/{row['id']}",
        json={"displayName": "Renamed", "isMandatory": False, "helpUrl": "https://help.example/x"},
    )
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched["displayName"] == "Renamed"
    assert patched["isMandatory"] is False
    assert patched["helpUrl"] == "https://help.example/x"

    # Deactivate
    r = await admin_client.patch(f"/admin/doc-requirements/{row['id']}", json={"isActive": False})
    assert r.status_code == 200
    assert r.json()["isActive"] is False

    # List without includeInactive hides it
    r = await admin_client.get("/admin/doc-requirements?country=IN")
    assert all(x["slug"] != slug for x in r.json())
    # With includeInactive it reappears
    r = await admin_client.get("/admin/doc-requirements?country=IN&includeInactive=true")
    assert any(x["slug"] == slug for x in r.json())


# QA-200.3 — slug regex rejected
@pytest.mark.parametrize(
    "bad_slug",
    [
        "UPPER",            # uppercase
        "has space",        # space
        "-leading",         # leading hyphen (must start with alphanumeric)
        "a" * 41,           # too long
        "trailing!",        # special char
    ],
)
async def test_slug_regex_rejected(admin_client, bad_slug):
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={"countryCode": "IN", "slug": bad_slug, "displayName": "test", "isMandatory": True},
    )
    assert r.status_code == 422, r.text


# QA-200.4 — unknown country code
async def test_unknown_country_rejected(admin_client):
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={"countryCode": "XX", "slug": "whatever", "displayName": "test", "isMandatory": True},
    )
    assert r.status_code == 422
    assert "Unknown country code" in r.text


# QA-200.5 — help_url scheme guard
@pytest.mark.parametrize(
    "bad_url",
    ["javascript:alert(1)", "data:text/html,<script>", "ftp://sketchy.com", "file:///etc/passwd"],
)
async def test_help_url_scheme_rejected(admin_client, bad_url):
    slug = uniq("qa200url").replace("-", "_")
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={
            "countryCode": "IN",
            "slug": slug,
            "displayName": "scheme guard test",
            "isMandatory": False,
            "helpUrl": bad_url,
        },
    )
    assert r.status_code == 422
    assert "http://" in r.text or "https://" in r.text


# QA-200.6 — duplicate active (country, slug) → 409
async def test_duplicate_active_conflict(admin_client):
    slug = uniq("qa200dup").replace("-", "_")
    body = {"countryCode": "IN", "slug": slug, "displayName": "First", "isMandatory": True}
    r = await admin_client.post("/admin/doc-requirements", json=body)
    assert r.status_code == 201
    r = await admin_client.post("/admin/doc-requirements", json=body)
    assert r.status_code == 409


# QA-200.7 — country / slug are immutable on PATCH (extra keys silently dropped)
async def test_country_and_slug_immutable_on_patch(admin_client):
    slug = uniq("qa200imm").replace("-", "_")
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={"countryCode": "IN", "slug": slug, "displayName": "test", "isMandatory": False},
    )
    row = r.json()
    r = await admin_client.patch(
        f"/admin/doc-requirements/{row['id']}",
        json={"countryCode": "US", "slug": "renamed_slug", "displayName": "post-patch"},
    )
    assert r.status_code == 200
    patched = r.json()
    assert patched["countryCode"] == "IN"
    assert patched["slug"] == slug
    assert patched["displayName"] == "post-patch"


# QA-200.8 — min_length on displayName
async def test_display_name_too_short(admin_client):
    slug = uniq("qa200name").replace("-", "_")
    r = await admin_client.post(
        "/admin/doc-requirements",
        json={"countryCode": "IN", "slug": slug, "displayName": "", "isMandatory": True},
    )
    assert r.status_code == 422
    assert "at least 2 characters" in r.text
