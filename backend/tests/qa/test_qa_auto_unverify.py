"""QA-800 — A verified business goes back to review when KYB data changes
(FLOW-800, adapted).

On main the trigger is what KYB checks: company name, registered address,
city, country, and required documents (Pegan's branch used the old seven
profile fields). Contact person and trade position no longer reopen review
— adapted assertions below.
"""
from __future__ import annotations

from conftest import fill_mandatory, signup_and_login
from qa_helpers import admin_add_doc_type, uniq, uniq_code, upload_entry, user_id_for


async def _verified_business(client, admin_client) -> str:
    email = f"{uniq('qa8')}@test.cor1x.co"
    await signup_and_login(client, email)
    await fill_mandatory(client)
    t = await admin_add_doc_type(admin_client, code=uniq_code("qa8"), name="QA8 cert")
    await upload_entry(client, type_id=t["id"])
    assert (await client.post("/me/submit-verification")).status_code == 200
    uid = await user_id_for(admin_client, email)
    r = await admin_client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 200 and r.json()["status"] == "verified"
    return email


async def _company(client, **over):
    biz = (await client.get("/me")).json()["business"]
    body = {
        "legalName": biz["legalName"], "industry": biz["industry"], "operatingCountries": biz["operatingCountries"],
        "addressLine": biz["addressLine"], "city": biz["city"], "country": biz["country"],
    } | over
    return await client.post("/onboarding/company", json=body)


# QA-800.1 — company name change → back to pending, review state cleared
async def test_company_name_edit_flips_back_to_pending(client, admin_client):
    await _verified_business(client, admin_client)
    assert (await _company(client, legalName="Edited Legal Name Pvt Ltd")).status_code == 200
    v = (await client.get("/me")).json()["verification"]
    assert v["status"] == "pending_verification" and v["verifiedAt"] is None
    assert v["rejectedReason"] is None and v["rejectedItems"] == []


# QA-800.2 — a non-KYB company field (website) keeps the badge
async def test_non_kyb_edit_stays_verified(client, admin_client):
    await _verified_business(client, admin_client)
    assert (await _company(client, websiteUrl="https://new-site.example.com")).status_code == 200
    assert (await client.get("/me")).json()["verification"]["status"] == "verified"


# QA-800.3 (adapted) — contact person change keeps the badge on main
async def test_primary_contact_edit_stays_verified(client, admin_client):
    await _verified_business(client, admin_client)
    r = await client.post("/onboarding/contact", json={"fullName": "Renamed Owner", "phone": "+91 98765 00099", "position": "Director"})
    assert r.status_code == 200
    assert (await client.get("/me")).json()["verification"]["status"] == "verified"


# QA-800.4 (adapted) — trade position change keeps the badge on main
async def test_trade_position_edit_stays_verified(client, admin_client):
    await _verified_business(client, admin_client)
    assert (await client.post("/onboarding/business", json={"tradePosition": "seller"})).status_code == 200
    assert (await client.get("/me")).json()["verification"]["status"] == "verified"


# QA-800.5 — approved documents stay approved after the flip
async def test_approved_docs_stay_approved_after_flip(client, admin_client):
    await _verified_business(client, admin_client)
    before = {d["id"]: d["status"] for d in (await client.get("/me/verification-docs")).json()}
    assert set(before.values()) == {"approved"}
    assert (await _company(client, legalName="Flipped Name Pvt Ltd")).status_code == 200
    after = {d["id"]: d["status"] for d in (await client.get("/me/verification-docs")).json()}
    assert after == before


# QA-800.6 (main) — address / city changes on the business profile also reopen review
async def test_address_edit_flips(client, admin_client):
    await _verified_business(client, admin_client)
    biz = (await client.get("/me")).json()["business"]
    r = await client.put(
        "/me/business-profile",
        json={"legalName": biz["legalName"], "country": "IN", "addressLine": "99 New Market Road", "city": biz["city"]},
    )
    assert r.status_code == 200 and r.json()["verification"]["status"] == "pending_verification"
