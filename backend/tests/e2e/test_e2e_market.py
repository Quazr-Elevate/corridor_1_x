"""E2E-MKT — the market: publishing lots, browsing them, unlocking a seller.

Two or three real businesses at a time, each with its own browser
(``make_client``), so these also prove the market behaves per-business and
not per-user. Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models.exchange_rate import ExchangeRate
from flows import list_lot, product_body, photo, sign_up, verified_trader

TODAY = date.today()


async def seed_rates(inr: str = "95", aed: str = "3.6725") -> None:
    """Today's USD rates, as the FX refresher would have stored them."""
    async with SessionLocal() as db:
        for quote, rate, source in (("INR", inr, "manual"), ("AED", aed, "pegged")):
            db.add(
                ExchangeRate(
                    base="USD", quote=quote, rate=Decimal(rate), as_of=TODAY, source=source, fetched_at=utcnow()
                )
            )
        await db.commit()


# ── Publishing and browsing ──────────────────────────────────────────


async def test_e2e_mkt_100_seller_publishes_buyer_browses(make_client, admin_client, counter):
    """E2E-MKT-100: a verified seller publishes a lot; an anonymous visitor
    finds it by search, filter and facet, and opens its detail page."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt100s")
    lot = await list_lot(seller, name="1121 Steam Basmati", variety="1121", originState="Haryana")
    await list_lot(seller, name="Soft Wheat Mill Grade", category="Wheat", variety="Lok-1", originState="Punjab")

    anon = make_client()
    listing = (await anon.get("/public/products")).json()
    assert listing["total"] == 2

    # Free-text search.
    hits = (await anon.get("/public/products?q=basmati")).json()
    assert hits["total"] == 1 and hits["items"][0]["id"] == lot["id"]

    # Category and origin filters.
    assert (await anon.get("/public/products?category=Wheat")).json()["total"] == 1
    assert (await anon.get("/public/products?originState=Haryana")).json()["total"] == 1
    assert (await anon.get("/public/products?category=Rice&originState=Punjab")).json()["total"] == 0

    # Facets mirror what's visible.
    facets = (await anon.get("/public/catalog/facets")).json()
    assert {c["value"] for c in facets["categories"]} == {"Rice", "Wheat"}
    assert {s["value"] for s in facets["originStates"]} == {"Haryana", "Punjab"}

    # Detail page: the gallery is there, the seller is not named.
    detail = (await anon.get(f"/public/products/{lot['id']}")).json()
    assert detail["name"] == "1121 Steam Basmati"
    assert detail["photos"] and detail["description"]
    assert detail["seller"]["sellerId"] == seller.business_id
    assert detail["seller"]["city"] == "Karnal"
    assert "businessName" not in detail["seller"] and "email" not in detail["seller"]


async def test_e2e_mkt_110_only_verified_businesses_reach_the_market(make_client, admin_client, counter):
    """E2E-MKT-110: draft and pending lots stay invisible; approval publishes
    them without the seller touching the listing again."""
    from flows import admin_verify, fill_passport, submit

    seller = await sign_up(make_client, counter, prefix="mkt110")
    lot = await list_lot(seller)
    anon = make_client()

    assert (await anon.get("/public/products")).json()["total"] == 0  # draft
    await fill_passport(seller)
    await submit(seller)
    assert (await anon.get("/public/products")).json()["total"] == 0  # pending isn't enough
    assert (await anon.get(f"/public/products/{lot['id']}")).status_code == 404

    await admin_verify(admin_client, seller)
    assert (await anon.get("/public/products")).json()["total"] == 1
    assert (await anon.get(f"/public/products/{lot['id']}")).status_code == 200


async def test_e2e_mkt_120_pagination_is_stable(make_client, admin_client, counter):
    """E2E-MKT-120: paging through the market returns every lot exactly once."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt120")
    for i in range(7):
        await list_lot(seller, name=f"Lot {i:02d}")

    anon = make_client()
    seen: list[str] = []
    for offset in (0, 3, 6):
        page = (await anon.get(f"/public/products?limit=3&offset={offset}")).json()
        assert page["total"] == 7
        seen += [item["id"] for item in page["items"]]
    assert len(seen) == 7 and len(set(seen)) == 7

    # Out-of-range offsets are empty, not errors.
    assert (await anon.get("/public/products?limit=3&offset=99")).json()["items"] == []
    assert (await anon.get("/public/products?limit=0")).status_code == 422
    assert (await anon.get("/public/products?limit=61")).status_code == 422


async def test_e2e_mkt_130_deleting_a_lot_removes_it_everywhere(make_client, admin_client, counter):
    """E2E-MKT-130: the seller withdraws a lot — gone from their list, from
    the market and from the detail route; a second delete 404s."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt130")
    lot = await list_lot(seller)
    anon = make_client()
    assert (await anon.get("/public/products")).json()["total"] == 1

    assert (await seller.client.delete(f"/products/{lot['id']}")).status_code == 204
    assert (await seller.client.get("/products")).json() == []
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{lot['id']}")).status_code == 404
    assert (await seller.client.delete(f"/products/{lot['id']}")).status_code == 404


# ── Multi-currency ───────────────────────────────────────────────────


async def test_e2e_mkt_200_prices_compare_across_currencies(make_client, admin_client, counter):
    """E2E-MKT-200: lots priced in INR, AED and USD keep their own price but
    get a comparable USD value, and a buyer can filter in their currency."""
    await seed_rates()
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt200")
    inr = await list_lot(seller, name="INR lot", pricePerUnit="9500", currency="INR")
    aed = await list_lot(seller, name="AED lot", pricePerUnit="367.25", currency="AED")
    usd = await list_lot(seller, name="USD lot", pricePerUnit="480", currency="USD")

    assert (inr["currency"], inr["priceUsd"]) == ("INR", "100.00")  # 9500 / 95
    assert (aed["currency"], aed["priceUsd"]) == ("AED", "100.00")  # 367.25 / 3.6725
    assert (usd["currency"], usd["priceUsd"]) == ("USD", "480.00")

    anon = make_client()
    rates = (await anon.get("/public/fx/rates")).json()
    assert rates["base"] == "USD" and rates["asOf"] == TODAY.isoformat()
    assert float(rates["rates"]["INR"]) == 95.0 and float(rates["rates"]["AED"]) == 3.6725

    # Filter in USD (the default).
    assert (await anon.get("/public/products?minPrice=200")).json()["total"] == 1
    assert (await anon.get("/public/products?maxPrice=150")).json()["total"] == 2

    # Filter in INR — the bound is converted, so the AED lot matches too.
    in_inr = (await anon.get("/public/products?maxPrice=10000&priceCurrency=INR")).json()
    assert {item["name"] for item in in_inr["items"]} == {"INR lot", "AED lot"}

    # Facets report the USD range.
    facets = (await anon.get("/public/catalog/facets")).json()
    assert facets["priceCurrency"] == "USD"
    assert facets["priceMin"] == "100.00" and facets["priceMax"] == "480.00"

    # An unsupported currency is refused at listing time.
    r = await seller.client.post(
        "/products", json=product_body([await photo(seller)], name="EUR lot", currency="EUR")
    )
    assert r.status_code == 400 and "INR, AED, USD" in r.json()["detail"]


async def test_e2e_mkt_210_display_currency_follows_the_trader(make_client, admin_client, counter):
    """E2E-MKT-210: an Indian business starts in INR and can switch; an
    unsupported choice is refused."""
    t = await verified_trader(make_client, admin_client, counter, prefix="mkt210")
    assert (await t.client.get("/me")).json()["displayCurrency"] == "INR"

    r = await t.client.patch("/me", json={"displayCurrency": "AED"})
    assert r.status_code == 200 and r.json()["displayCurrency"] == "AED"
    assert (await t.client.get("/me")).json()["displayCurrency"] == "AED"

    bad = await t.client.patch("/me", json={"displayCurrency": "JPY"})
    assert bad.status_code in (400, 422)


# ── Contact reveal ───────────────────────────────────────────────────


async def test_e2e_mkt_300_verified_buyer_unlocks_a_seller(make_client, admin_client, counter):
    """E2E-MKT-300: the core trade moment — a verified buyer unlocks a
    verified seller's contact once, and sees the same card afterwards."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt300s")
    buyer = await verified_trader(make_client, admin_client, counter, prefix="mkt300b")
    lot = await list_lot(seller)

    r = await buyer.client.post(f"/products/{lot['id']}/contact-reveal")
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["sellerId"] == seller.business_id
    assert card["email"] == seller.email
    assert card["fullName"] == "Asha Rao"
    assert card["businessName"] and card["city"] == "Karnal" and card["country"] == "IN"
    assert card["revealedAt"]

    # Idempotent: unlocking again is the same card, not a second charge.
    again = await buyer.client.post(f"/products/{lot['id']}/contact-reveal")
    assert again.status_code == 200
    assert again.json()["revealedAt"] == card["revealedAt"]


async def test_e2e_mkt_310_reveal_is_gated_on_both_sides(make_client, admin_client, counter):
    """E2E-MKT-310: anonymous visitors, unverified buyers and sellers who
    lost verification all get nothing."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt310s")
    lot = await list_lot(seller)

    # Anonymous.
    assert (await make_client().post(f"/products/{lot['id']}/contact-reveal")).status_code == 401

    # Signed in but not verified.
    draft = await sign_up(make_client, counter, prefix="mkt310d")
    r = await draft.client.post(f"/products/{lot['id']}/contact-reveal")
    assert r.status_code == 403, r.text

    # Verified buyer, seller revoked → the lot isn't in the market any more.
    buyer = await verified_trader(make_client, admin_client, counter, prefix="mkt310b")
    from flows import admin_reject

    await admin_reject(admin_client, seller, reason="Licence expired.", items=["legalName"])
    assert (await buyer.client.post(f"/products/{lot['id']}/contact-reveal")).status_code == 404


async def test_e2e_mkt_320_you_cannot_unlock_yourself(make_client, admin_client, counter):
    """E2E-MKT-320: a business can't reveal its own contact, and a bad id is
    a 404, not a 500."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="mkt320")
    lot = await list_lot(seller)

    r = await seller.client.post(f"/products/{lot['id']}/contact-reveal")
    assert r.status_code == 400, r.text
    assert (await seller.client.post("/products/not-a-uuid/contact-reveal")).status_code == 404
    assert (
        await seller.client.post("/products/00000000-0000-4000-8000-000000000000/contact-reveal")
    ).status_code == 404
