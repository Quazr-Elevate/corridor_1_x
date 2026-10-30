"""QA-300 / 400 / 500 — Trader doc requirements, upload replace, submit gate."""
from __future__ import annotations

import pytest

from tests.qa.conftest import (
    TINY_PNG,
    admin_add_requirement,
    fill_profile_and_submit,
    signup_and_login,
    uniq,
    upload_slot_doc,
)


async def _signup(client, country: str = "IN"):
    email = f"{uniq('qa3')}@test.cor1x.co"
    await signup_and_login(client, email, country=country)
    return email


# QA-300.1 — unauthenticated → 401
async def test_requirements_requires_auth(make_client):
    anon = make_client()
    r = await anon.get("/me/verification-docs/requirements")
    assert r.status_code == 401


# QA-300.2 — new catalog row shows up for the trader's country
async def test_new_catalog_row_visible_to_trader(client, admin_client):
    await _signup(client, country="IN")
    slug = uniq("qa300").replace("-", "_")
    await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="QA300 Doc")
    r = await client.get("/me/verification-docs/requirements")
    assert r.status_code == 200
    required = r.json()["required"]
    hits = [s for s in required if s["slug"] == slug]
    assert hits, f"slot not found; required={required}"
    assert hits[0]["displayName"] == "QA300 Doc"
    assert hits[0]["isMandatory"] is True


# QA-300.3 — admin IN requirement NOT visible to a UAE trader
async def test_other_country_requirement_not_visible(client, admin_client, make_client):
    await _signup(client, country="IN")
    slug = uniq("qa300iso").replace("-", "_")
    await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="India-only")
    # Second trader in a different country
    uae = make_client()
    await signup_and_login(uae, f"{uniq('qa3uae')}@test.cor1x.co", country="AE")
    r = await uae.get("/me/verification-docs/requirements")
    assert r.status_code == 200
    assert all(s["slug"] != slug for s in r.json()["required"])


# QA-400.1 — upload against a known slot works, DocOut carries slug + display name
async def test_upload_fills_slot_and_populates_display_name(client, admin_client):
    await _signup(client, country="IN")
    slug = uniq("qa400").replace("-", "_")
    req = await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="QA400 Doc")
    doc = await upload_slot_doc(client, slot_id=req["id"], slug=slug)
    assert doc["requirementSlug"] == slug
    assert doc["requirementDisplayName"] == "QA400 Doc"
    # /me/verification-docs also populates these (QA-fix in-pass earlier).
    r = await client.get("/me/verification-docs")
    assert r.status_code == 200
    docs = r.json()
    hits = [d for d in docs if d["requirementSlug"] == slug]
    assert len(hits) == 1
    assert hits[0]["requirementDisplayName"] == "QA400 Doc"


# QA-400.2 — second upload replaces the first (same slot = at most one row)
async def test_replace_on_upload(client, admin_client):
    await _signup(client, country="IN")
    slug = uniq("qa400rep").replace("-", "_")
    req = await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="QA400 replace")
    first = await upload_slot_doc(client, slot_id=req["id"], slug=slug, filename="first.png")
    second = await upload_slot_doc(client, slot_id=req["id"], slug=slug, filename="second.png")
    assert first["id"] != second["id"]
    r = await client.get("/me/verification-docs/requirements")
    required = r.json()["required"]
    hit = next(s for s in required if s["slug"] == slug)
    assert hit["upload"]["filename"] == "second.png"
    # Trader's doc list has only ONE row for this slot.
    r = await client.get("/me/verification-docs")
    docs = [d for d in r.json() if d["requirementSlug"] == slug]
    assert len(docs) == 1
    assert docs[0]["filename"] == "second.png"


# QA-400.3 — cross-country slot id rejected
async def test_cross_country_slot_rejected(client, admin_client):
    await _signup(client, country="IN")
    ae_slug = uniq("qa400ae").replace("-", "_")
    ae_req = await admin_add_requirement(admin_client, country="AE", slug=ae_slug, display_name="AE only")
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": ae_slug, "required_doc_type_id": ae_req["id"]},
        files={"file": ("cert.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 400
    assert "different country" in r.text


# QA-400.4 — non-existent / inactive slot id rejected
async def test_unknown_slot_rejected(client):
    await _signup(client, country="IN")
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "whatever", "required_doc_type_id": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("cert.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 400


# QA-500.1 — submit before mandatory docs → 400 with doc name
async def test_submit_blocked_without_mandatory_docs(client, admin_client):
    from tests.conftest import fill_mandatory
    await _signup(client, country="IN")
    await fill_mandatory(client)  # all 7 profile fields
    slug = uniq("qa500").replace("-", "_")
    await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="Required for QA500")
    r = await client.post("/me/submit-verification")
    assert r.status_code == 400
    assert "Required for QA500" in r.json()["detail"]


# QA-500.2 — once uploaded, submit lands + verification_state shape correct
async def test_submit_success_once_all_filled(client, admin_client):
    from tests.conftest import fill_mandatory
    await _signup(client, country="IN")
    await fill_mandatory(client)
    slug = uniq("qa500ok").replace("-", "_")
    req = await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="QA500 OK")
    await upload_slot_doc(client, slot_id=req["id"], slug=slug)
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "pending_verification"
    assert state["missing"] == []
    # mandatory_total = 7 profile fields + however many active mandatory
    # requirements exist for the user's country at submit time.
    assert state["mandatoryTotal"] >= 8


# QA-500.3 — mandatoryTotal reflects live catalog (adding a req bumps it)
async def test_mandatory_total_tracks_catalog(client, admin_client):
    from tests.conftest import fill_mandatory
    await _signup(client, country="IN")
    before = (await client.get("/me")).json()["verification"]["mandatoryTotal"]
    slug = uniq("qa500live").replace("-", "_")
    await admin_add_requirement(admin_client, country="IN", slug=slug, display_name="live")
    after = (await client.get("/me")).json()["verification"]["mandatoryTotal"]
    assert after == before + 1
