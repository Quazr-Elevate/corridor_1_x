"""Issues from the tester's report (docs/testing/Book1.xlsx), one test per
issue the backend can prove. #1, #2 and #16 are screen fixes."""
from __future__ import annotations

from datetime import timedelta

from conftest import (
    complete_listing,
    fill_mandatory,
    publish_listing,
    set_status,
    signup_and_login,
    verify_business,
)
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models.admin_action import AdminAction
from app.models.business import BusinessStatus

SCRIPT = "<script>alert(1)</script>"


async def _verified(client, admin_client, email="b1@kaverifoods.in") -> dict:
    me = await signup_and_login(client, email)
    await fill_mandatory(client)
    assert (await client.post("/me/submit-verification")).status_code == 200
    assert (await verify_business(admin_client, me["userId"])).status_code == 200
    return me


async def _patch(admin_client, user_id: str, **business) -> object:
    return await admin_client.patch(f"/admin/users/{user_id}", json={"businessProfile": business})


# ── Console: editing a business (#3, #5, #6, #7, #8) ─────────────────


async def test_3_a_bad_country_names_the_field_not_the_validator(client, admin_client):
    me = await signup_and_login(client, "b3@kaverifoods.in")
    r = await _patch(admin_client, me["userId"], country="dsd")
    assert r.status_code == 422
    body = r.json()
    assert body["fields"][0]["field"] == "businessProfile.country"
    assert "function-after" not in body["detail"] and "validator" not in body["detail"]
    assert "Choose a country from the list" in body["detail"]


async def test_5_a_country_not_onboarded_is_a_clean_400(client, admin_client):
    me = await signup_and_login(client, "b5@kaverifoods.in")
    r = await _patch(admin_client, me["userId"], country="US")
    assert r.status_code == 400
    assert r.json()["detail"] == "That country isn't onboarded yet. Choose one of: AE, IN."


async def test_6_a_verified_business_keeps_its_country_while_it_holds_that_countrys_documents(client, admin_client):
    me = await _verified(client, admin_client)
    r = await _patch(admin_client, me["userId"], country="AE")
    assert r.status_code == 400 and "belongs to its current country" in r.json()["detail"]
    detail = (await admin_client.post(f"/admin/users/{me['userId']}/open", json={"reason": "Checking the country"})).json()
    assert detail["businessProfile"]["country"] == "IN" and detail["status"] == "verified"


async def test_6_7_a_console_edit_to_a_kyb_field_sends_a_verified_business_back_to_review(client, admin_client):
    me = await _verified(client, admin_client, "b6@kaverifoods.in")
    r = await _patch(admin_client, me["userId"], city="Pune")
    assert r.status_code == 200 and r.json()["status"] == "pending_verification"
    async with SessionLocal() as db:
        row = (await db.scalars(
            select(AdminAction).where(AdminAction.action == "business.update").order_by(AdminAction.created_at.desc())
        )).first()
    assert row.details["reopenedReview"] is True
    # A field KYB doesn't check leaves the badge alone.
    await set_status(me["userId"], BusinessStatus.verified)
    r = await _patch(admin_client, me["userId"], industry="Spices")
    assert r.status_code == 200 and r.json()["status"] == "verified"


async def test_7_a_mandatory_field_cant_be_blanked(client, admin_client):
    me = await _verified(client, admin_client, "b7@kaverifoods.in")
    for field, label in (("addressLine", "Registered address"), ("legalName", "Company name"), ("city", "City")):
        r = await _patch(admin_client, me["userId"], **{field: ""})
        assert r.status_code == 400 and r.json()["detail"].startswith(f"{label} is required"), field


async def test_8_11_17_markup_is_refused_where_people_type(client, admin_client):
    me = await signup_and_login(client, "b8@kaverifoods.in")
    r = await _patch(admin_client, me["userId"], legalName=SCRIPT)
    assert r.status_code == 422 and "plain text" in r.json()["detail"]
    r = await client.post("/onboarding/company", json={"legalName": SCRIPT, "industry": "Rice", "operatingCountries": ["IN"]})
    assert r.status_code == 422

    await set_status(me["userId"], BusinessStatus.verified)
    draft = (await client.post("/products", json={"name": "Sona Masoori", "category": "Rice"})).json()
    for field in ("name", "variety", "grade", "description"):
        r = await client.patch(f"/products/{draft['id']}", json={field: f"Fine rice {SCRIPT}"})
        assert r.status_code == 422 and r.json()["fields"][0]["field"] == field, field

    r = await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": SCRIPT})
    assert r.status_code == 422
    rfq = (await client.post("/rfqs", json={"kind": "open", "category": "Rice", "productName": "Basmati"})).json()
    for field in ("productName", "variety", "grade", "notes"):
        r = await client.patch(f"/rfqs/{rfq['id']}", json={field: f"x {SCRIPT}"})
        assert r.status_code == 422, field

    # A comparison is not markup.
    r = await client.patch(f"/products/{draft['id']}", json={"description": "Moisture < 12% and broken > 2% rejected."})
    assert r.status_code == 200, r.text


# ── Listings (#9, #10, #12–#15) ──────────────────────────────────────


async def _published(client, admin_client, email="s9@kaverifoods.in") -> dict:
    me = await signup_and_login(client, email)
    await set_status(me["userId"], BusinessStatus.verified)
    listing = await complete_listing(client)
    await publish_listing(client, admin_client, listing["id"])
    return listing


async def test_9_a_big_price_swing_on_a_live_listing_waits_for_review(client, make_client, admin_client):
    listing = await _published(client, admin_client)
    pid = listing["id"]
    # Prices show only to a verified business.
    anon = make_client()
    buyer = await signup_and_login(anon, "buyer9@othermill.in")
    await set_status(buyer["userId"], BusinessStatus.verified)

    # Within 20%: applies at once, as before.
    r = await client.patch(f"/products/{pid}", json={"priceMin": "78.00", "priceMax": "85.00"})
    assert r.status_code == 200 and r.json()["priceMin"] == "78.00" and not r.json()["hasPendingRevision"]

    # ₹78 → ₹1 is a swing: the market keeps the approved price.
    r = await client.patch(f"/products/{pid}", json={"priceMin": "1.00", "priceMax": "2.00"})
    assert r.status_code == 200
    body = r.json()
    assert body["priceMin"] == "78.00" and body["hasPendingRevision"]
    assert body["pendingRevision"]["priceMin"] == "1.00" and body["pendingRevision"]["priceMax"] == "2.00"
    public = (await anon.get(f"/public/products/{pid}")).json()
    assert public["priceMin"] == "78.00"

    # A new currency also waits.
    r = await client.patch(f"/products/{pid}", json={"currency": "USD"})
    assert r.json()["currency"] == "INR" and r.json()["pendingRevision"]["currency"] == "USD"

    # Approved, the new price goes live with its USD mirror.
    assert (await admin_client.post(f"/admin/listings/{pid}/approve")).status_code == 200
    public = (await anon.get(f"/public/products/{pid}")).json()
    assert public["priceMin"] == "1.00" and public["currency"] == "USD"


async def test_10_a_reject_reason_must_say_something(client, admin_client):
    me = await signup_and_login(client, "s10@kaverifoods.in")
    await set_status(me["userId"], BusinessStatus.verified)
    listing = await complete_listing(client)
    assert (await client.post(f"/products/{listing['id']}/submit")).status_code == 200
    r = await admin_client.post(f"/admin/listings/{listing['id']}/reject", json={"reason": "x"})
    assert r.status_code == 400 and "at least 10 characters" in r.json()["detail"]
    r = await admin_client.post(f"/admin/listings/{listing['id']}/reject", json={"reason": "The photo shows a logo."})
    assert r.status_code == 200


async def test_12_13_14_a_draft_is_checked_when_saved(client):
    me = await signup_and_login(client, "s12@kaverifoods.in")
    await set_status(me["userId"], BusinessStatus.verified)
    pid = (await client.post("/products", json={"name": "Sona Masoori", "category": "Rice"})).json()["id"]

    r = await client.patch(f"/products/{pid}", json={"originCountry": "US"})
    assert r.status_code == 400 and "AE, IN" in r.json()["detail"]
    assert (await client.patch(f"/products/{pid}", json={"originCountry": "AE"})).status_code == 200

    for body in ({"priceMin": "0"}, {"priceMin": "10", "priceMax": "0"}):
        r = await client.patch(f"/products/{pid}", json=body)
        assert r.status_code == 422 and "greater than 0" in r.json()["detail"], body

    past = (utcnow().date() - timedelta(days=1)).isoformat()
    r = await client.patch(f"/products/{pid}", json={"priceValidUntil": past})
    assert r.status_code == 400 and "has passed" in r.json()["detail"]
    today = utcnow().date().isoformat()
    assert (await client.patch(f"/products/{pid}", json={"priceValidUntil": today})).status_code == 200


async def test_15_an_edit_to_a_live_listing_says_it_is_waiting(client, admin_client):
    listing = await _published(client, admin_client, "s15@kaverifoods.in")
    r = await client.patch(f"/products/{listing['id']}", json={"name": "Totally different product"})
    assert r.status_code == 200
    body = r.json()
    assert body["hasPendingRevision"] is True
    assert body["name"] == listing["name"] and body["pendingRevision"]["name"] == "Totally different product"
