from __future__ import annotations

from conftest import fill_mandatory, signup_and_login


async def test_onboarding_saves_and_status(client):
    await signup_and_login(client, "o1@kaverifoods.in")
    st = (await client.get("/onboarding/status")).json()
    assert st == {"companyInfoDone": False, "primaryContactDone": False, "businessProfileDone": False}
    await fill_mandatory(client)
    st = (await client.get("/onboarding/status")).json()
    assert st["companyInfoDone"] and st["primaryContactDone"] and st["businessProfileDone"]

    me = (await client.get("/me")).json()
    assert me["businessName"] == "Acme Agro 1 Pvt Ltd"
    assert me["business"]["operatingCountries"] == ["IN"]
    # Person fields land on the user, company fields on the business.
    assert me["primary"] == {"fullName": "Asha Rao", "phone": "+91 98765 00001", "position": "Director"}
    assert me["business"]["tradePosition"] == "both"
    assert me["verification"]["missing"] == []
    assert me["status"] == "draft"  # saving never submits


async def test_countries_are_alpha2(client):
    await signup_and_login(client, "c1@kaverifoods.in")
    r = await client.post(
        "/onboarding/company",
        json={"legalName": "Alpha Co", "industry": "Rice", "operatingCountries": ["IND", "ae", " SA "], "entityType": "llp"},
    )
    assert r.status_code == 200, r.text
    b = (await client.get("/me")).json()["business"]
    assert b["operatingCountries"] == ["IN", "AE", "SA"] and b["entityType"] == "llp"
    r = await client.post(
        "/onboarding/company", json={"legalName": "Alpha Co", "industry": "Rice", "operatingCountries": ["XX"]}
    )
    assert r.status_code == 422
    r = await client.post("/onboarding/business", json={"tradePosition": "seller", "targetMarkets": ["Atlantis"]})
    assert r.status_code == 422


async def test_onboarding_validation(client):
    await signup_and_login(client, "o2@kaverifoods.in")
    r = await client.post("/onboarding/business", json={"tradePosition": "pirate"})
    assert r.status_code == 422
    r = await client.post("/onboarding/contact", json={"fullName": "R2D2"})
    assert r.status_code == 422
    r = await client.post(
        "/onboarding/company", json={"legalName": "A" * 201, "industry": "x", "operatingCountries": ["IN"]}
    )
    assert r.status_code == 422


async def test_uniqueness_conflicts(client, make_client):
    await signup_and_login(client, "u1@kaverifoods.in")
    r = await client.post(
        "/onboarding/company",
        json={
            "legalName": "Kaveri Foods  Pvt Ltd",
            "industry": "Rice",
            "operatingCountries": ["IN"],
            "websiteUrl": "https://www.KaveriFoods.in/",
        },
    )
    assert r.status_code == 200
    r = await client.post("/onboarding/contact", json={"fullName": "Asha", "phone": "+91 98765 43210"})
    assert r.status_code == 200
    # Re-saving your own values is fine.
    r = await client.post("/onboarding/contact", json={"fullName": "Asha", "phone": "+919876543210"})
    assert r.status_code == 200

    other = make_client()
    await signup_and_login(other, "u2@othermill.in")
    r = await other.post(
        "/onboarding/company",
        json={"legalName": "kaveri foods pvt ltd", "industry": "Rice", "operatingCountries": ["IN"]},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "This legal company name is already registered on Cor1x."
    r = await other.post(
        "/onboarding/company",
        json={"legalName": "Other Mill", "industry": "Rice", "operatingCountries": ["IN"], "websiteUrl": "kaverifoods.in"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "This website is already linked to another Cor1x account."
    r = await other.post("/onboarding/contact", json={"fullName": "Bo", "phone": "+91-98765-43210"})
    assert r.status_code == 409
    assert r.json()["detail"] == "This phone number is already registered on Cor1x."


async def test_unique_index_race_maps_to_409(client, make_client, monkeypatch):
    """Simulate a race: the friendly pre-check passes, the UNIQUE index fires."""
    import app.modules.accounts.service as accounts

    await signup_and_login(client, "r1@kaverifoods.in")
    r = await client.post("/onboarding/contact", json={"fullName": "Asha", "phone": "+91 90000 11111"})
    assert r.status_code == 200

    async def no_check(*_a, **_k):
        return None

    monkeypatch.setattr(accounts, "ensure_phone_available", no_check)
    other = make_client()
    await signup_and_login(other, "r2@othermill.in")
    r = await other.post("/onboarding/contact", json={"fullName": "Bo", "phone": "+919000011111"})
    assert r.status_code == 409
    assert r.json()["detail"] == "This phone number is already registered on Cor1x."


async def test_submit_verification(client):
    await signup_and_login(client, "s1@kaverifoods.in")
    r = await client.post("/me/submit-verification")
    assert r.status_code == 400
    assert "Missing" in r.json()["detail"]
    await fill_mandatory(client)
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_verification"
    # idempotent
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200 and r.json()["status"] == "pending_verification"
    assert r.json()["submittedAt"]


async def test_delete_me_releases_unique_keys(client, make_client):
    await signup_and_login(client, "d1@kaverifoods.in")
    await fill_mandatory(client, n=7)
    r = await client.delete("/me")
    assert r.status_code == 204
    assert (await client.get("/me")).status_code == 401

    other = make_client()
    await signup_and_login(other, "d2@othermill.in")
    await fill_mandatory(other, n=7)  # same legal name + phone — now free (partial unique indexes)
    # The deleted account's email is no longer "taken" (only the resend
    # cooldown of its old signup code applies).
    again = make_client()
    r = await again.post("/auth/signup/code", json={"email": "d1@kaverifoods.in"})
    assert r.status_code == 429 and "wait" in r.json()["detail"]


async def test_company_address_and_socials(client):
    await signup_and_login(client, "addr1@kaverifoods.in")
    base = {"legalName": "Addr Co", "industry": "Rice", "operatingCountries": ["IN"]}
    r = await client.post(
        "/onboarding/company",
        json={
            **base,
            "entityType": "private_ltd",
            "addressLine": " 12 Market Road ",
            "city": "Mysuru",
            "state": "Karnataka",
            "pincode": "570001",
            "country": "IND",
            "googleBusinessUrl": "https://g.page/addr",
            "facebookUrl": "https://facebook.com/addr",
        },
    )
    assert r.status_code == 200, r.text
    b = (await client.get("/me")).json()["business"]
    assert b["addressLine"] == "12 Market Road" and b["city"] == "Mysuru" and b["state"] == "Karnataka"
    assert b["pincode"] == "570001" and b["country"] == "IN" and b["entityType"] == "private_ltd"
    assert b["googleBusinessUrl"] == "https://g.page/addr" and b["facebookUrl"] == "https://facebook.com/addr"

    # Omitted fields are left alone; blank strings clear optional ones.
    r = await client.post("/onboarding/company", json={**base, "facebookUrl": "", "country": "ae"})
    assert r.status_code == 200, r.text
    b = (await client.get("/me")).json()["business"]
    assert b["city"] == "Mysuru" and b["facebookUrl"] is None and b["country"] == "AE"

    for bad in ({"pincode": "1" * 11}, {"country": "XX"}, {"city": "x" * 101}, {"googleBusinessUrl": "u" * 301}):
        r = await client.post("/onboarding/company", json={**base, **bad})
        assert r.status_code == 422, bad
