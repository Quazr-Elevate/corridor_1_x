"""The shared leak filter (CX-087): what it blocks, what it sends to a
reviewer, and the ordinary trade text it must leave alone."""
from __future__ import annotations

import pytest
from conftest import signup_and_login

from app.shared.leakfilter import Verdict, check, check_all, mentions


@pytest.mark.parametrize(
    "text, reason",
    [
        ("Call 98765 43210 for the best rate", "phone number"),
        ("ph: +91-98765-43210", "phone number"),
        ("Dubai office (050) 123 4567", "phone number"),
        ("nine eight seven six five four three two one zero", "phone number"),
        ("my number is nine 8 seven 6 five double four three two one", "phone number"),
        ("nau aath saat chhe paanch char teen do ek shunya", "phone number"),
        ("write to sales@kaverifoods.in", "email address"),
        ("sales at kaverifoods dot in", "email address"),
        ("sales(at)kaverifoods(dot)in", "email address"),
        ("see www.kaverifoods.in for photos", "web address"),
        ("catalogue on kaverifoods.com/rice", "web address"),
        ("https://wa.me/919876543210", "web address"),
        ("message @kaveri_foods", "messaging handle"),
    ],
)
def test_blocked(text, reason):
    result = check(text)
    assert result.verdict is Verdict.BLOCKED and result.blocked
    assert reason in result.reasons


@pytest.mark.parametrize(
    "text, reason",
    [
        ("WhatsApp for samples", "asks to be contacted directly"),
        ("contact us for a quote", "asks to be contacted directly"),
        ("Milled by Kaveri Foods Pvt Ltd", "may name a company"),
        ("Supplied by Gulf Grain LLC", "may name a company"),
        ("Sharma & Sons quality", "may name a company"),
    ],
)
def test_sent_to_review(text, reason):
    result = check(text)
    assert result.verdict is Verdict.REVIEW and not result.blocked
    assert reason in result.reasons


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "1121 Steam Basmati, 2025 2026 crop, sortex cleaned",
        "Moisture max 12 %, broken 2 %, grain length 8.3 mm",
        "500 MT available, MOQ 25 MT, 50 kg PP bags, 14 days lead time",
        "Price 72000 to 78000 per MT, FOB Mundra, HS 100630",
        "Two grades, one for export and one for domestic. Packed in 5, 10 and 25 kg.",
        "Ships in two to three weeks from the mill at 30 C storage",
        "Grade A at 5% broken; ISO 22000 and FSSAI certified mill",
    ],
)
def test_ordinary_listing_text_passes(text):
    assert check(text).verdict is Verdict.PASS


def test_block_wins_over_review_and_lists_every_reason():
    result = check("Kaveri Foods Pvt Ltd, WhatsApp 98765 43210 or sales@kaverifoods.in")
    assert result.verdict is Verdict.BLOCKED
    assert set(result.reasons) == {"phone number", "email address"}


def test_check_all_returns_only_the_fields_that_fail():
    found = check_all({"name": "1121 Basmati", "description": "call me on 9876543210", "grade": None})
    assert list(found) == ["description"]


def test_mentions_finds_the_company_name_without_its_suffix():
    assert mentions("From the Kaveri  Foods mill in Karnal", "Kaveri Foods Pvt Ltd")
    assert mentions("KAVERI-FOODS premium", "Kaveri Foods Pvt Ltd")
    assert not mentions("Premium basmati from Haryana", "Kaveri Foods Pvt Ltd")
    assert not mentions("anything", None)


async def test_listing_text_goes_through_the_filter(client, admin_client):
    await signup_and_login(client, "seller@kaverifoods.in", company_name="Kaveri Foods Pvt Ltd")
    r = await client.post("/products", json={"name": "Basmati call 9876543210", "category": "Rice"})
    assert r.status_code == 400 and "phone number" in r.json()["detail"]
    r = await client.post("/products", json={"name": "1121 Basmati", "category": "Rice", "description": "mail sales@kaverifoods.in"})
    assert r.status_code == 400 and "email address" in r.json()["detail"] and "description" in r.json()["detail"].lower()

    r = await client.post("/products", json={"name": "1121 Basmati", "category": "Rice"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = await client.patch(f"/products/{pid}", json={"description": "see www.kaverifoods.in"})
    assert r.status_code == 400 and "web address" in r.json()["detail"]
    # Text that only needs a second look is saved, and the reviewer is told why.
    r = await client.patch(f"/products/{pid}", json={"description": "From the Kaveri Foods mill. WhatsApp for samples."})
    assert r.status_code == 200, r.text
    detail = (await admin_client.get(f"/admin/listings/{pid}")).json()
    assert detail["leakFlags"] == [
        {"field": "description", "reasons": ["asks to be contacted directly", "names the seller"]}
    ]
