"""QA-800 — Verified business re-edit auto-unverify (FLOW-800)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.business import Business, BusinessStatus
from app.models.user import User
from tests.conftest import SessionLocal, fill_mandatory, set_status, signup_and_login
from tests.qa.conftest import (
    admin_add_requirement,
    uniq,
    upload_slot_doc,
)


async def _verified_business(client, admin_client, *, country: str = "IN") -> str:
    """Signup → fill → upload required doc → submit → admin verify.
    Returns the user's email."""
    email = f"{uniq('qa8')}@test.cor1x.co"
    await signup_and_login(client, email, country=country)
    await fill_mandatory(client)
    slug = uniq("qa8").replace("-", "_")
    req = await admin_add_requirement(admin_client, country=country, slug=slug, display_name="QA8 cert")
    await upload_slot_doc(client, slot_id=req["id"], slug=slug)
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200
    # Find user_id via admin lookup
    users = (await admin_client.get(f"/admin/users?q={email}")).json()["items"]
    uid = next(u["userId"] for u in users if u["email"] == email)
    r = await admin_client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 200 and r.json()["status"] == "verified"
    return email


# QA-800.1 — Mandatory profile change on verified biz → auto back to pending
async def test_mandatory_edit_flips_back_to_pending(client, admin_client):
    await _verified_business(client, admin_client)
    assert (await client.get("/me")).json()["verification"]["status"] == "verified"
    # Change legalName (one of the 7 mandatory fields)
    r = await client.post(
        "/onboarding/company",
        json={
            "legalName": "Edited Legal Name Pvt Ltd",
            "industry": "Rice",
            "operatingCountries": ["IN"],
        },
    )
    assert r.status_code == 200
    me = (await client.get("/me")).json()
    v = me["verification"]
    assert v["status"] == "pending_verification"
    assert v["verifiedAt"] is None
    # Previous reject state (if any) is cleared on auto-flip
    assert v["rejectedReason"] is None
    assert v["rejectedItems"] in (None, [])


# QA-800.2 — Non-mandatory edit on verified biz does NOT flip
async def test_non_mandatory_edit_stays_verified(client, admin_client):
    await _verified_business(client, admin_client)
    # Keep legalName/industry/op countries the same; only change website_url.
    me_before = (await client.get("/me")).json()
    biz = me_before["business"]
    r = await client.post(
        "/onboarding/company",
        json={
            "legalName": biz["legalName"],
            "industry": biz["industry"],
            "operatingCountries": biz["operatingCountries"],
            "websiteUrl": "https://new-site.example.com",
        },
    )
    assert r.status_code == 200
    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "verified"


# QA-800.3 — Primary contact change (fullName) also flips
async def test_primary_contact_mandatory_edit_flips(client, admin_client):
    await _verified_business(client, admin_client)
    r = await client.post(
        "/onboarding/contact",
        json={"fullName": "Renamed Owner", "phone": "+91 98765 00099", "position": "Director"},
    )
    assert r.status_code == 200
    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "pending_verification"


# QA-800.4 — Business trade_position change flips
async def test_trade_position_edit_flips(client, admin_client):
    await _verified_business(client, admin_client)
    me = (await client.get("/me")).json()
    current = me["business"]["tradePosition"]
    new = "seller" if current != "seller" else "buyer"
    r = await client.post("/onboarding/business", json={"tradePosition": new})
    assert r.status_code == 200
    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "pending_verification"


# QA-800.5 — Verified doc stays approved after flip (admin re-reviews with new fields)
async def test_approved_cert_stays_approved_after_flip(client, admin_client):
    await _verified_business(client, admin_client)
    # Capture the current approved cert id
    docs = (await client.get("/me/verification-docs")).json()
    cert = next(d for d in docs if d["requirementSlug"])
    assert cert["status"] == "approved"
    # Flip
    r = await client.post(
        "/onboarding/company",
        json={"legalName": "Flipped Name Pvt Ltd", "industry": "Rice", "operatingCountries": ["IN"]},
    )
    assert r.status_code == 200
    # Cert should still be approved — the admin's new review will cover the whole package.
    docs = (await client.get("/me/verification-docs")).json()
    cert2 = next(d for d in docs if d["id"] == cert["id"])
    assert cert2["status"] == "approved"
