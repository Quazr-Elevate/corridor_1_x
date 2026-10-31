"""QA-100 — Country (FLOW-100, adapted).

Pegan's branch asked for the country at sign-up; on main (product decision)
sign-up asks for name, company and work email, and the country is chosen on
the business profile from countries Corridor ops has set up. Same checks:
required/valid ISO code, normalisation (lower-case, alpha-3), persistence.
"""
from __future__ import annotations

from conftest import signup_and_login
from qa_helpers import set_country, uniq


# QA-100.1 — sign-up needs no country; the business starts in IN (INR)
async def test_signup_defaults_country_to_india(client):
    await signup_and_login(client, f"{uniq('qa100')}@test.cor1x.co")
    me = (await client.get("/me")).json()
    assert me["business"]["country"] == "IN" and me["displayCurrency"] == "INR"


# QA-100.2 — unknown ISO code on the profile → 422
async def test_profile_country_invalid_rejected(client):
    await signup_and_login(client, f"{uniq('qa100')}@test.cor1x.co")
    r = await set_country(client, "XX")
    assert r.status_code == 422 and "Unknown country code" in r.text


# QA-100.3 — lower-case normalised
async def test_profile_country_lowercase_normalized(client):
    await signup_and_login(client, f"{uniq('qa100')}@test.cor1x.co")
    r = await set_country(client, "ae")
    assert r.status_code == 200, r.text
    assert r.json()["business"]["country"] == "AE"


# QA-100.4 — alpha-3 normalised
async def test_profile_country_alpha3_normalized(client):
    await signup_and_login(client, f"{uniq('qa100')}@test.cor1x.co")
    r = await set_country(client, "ARE")
    assert r.status_code == 200, r.text
    assert r.json()["business"]["country"] == "AE"


# QA-100.5 (main) — a valid country that isn't set up can't be picked
async def test_profile_country_not_set_up_rejected(client):
    await signup_and_login(client, f"{uniq('qa100')}@test.cor1x.co")
    r = await set_country(client, "US")
    assert r.status_code == 400 and "doesn’t onboard" in r.json()["detail"]
