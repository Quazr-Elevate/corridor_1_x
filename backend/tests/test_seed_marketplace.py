"""scripts/seed_marketplace.py: verified buyers and sellers with live,
matchable listings; a second run adds nothing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_marketplace  # noqa: E402


async def test_seed_makes_verified_traders_with_live_listings(client, make_client, capsys):
    await seed_marketplace.main()
    await seed_marketplace.main()  # idempotent
    out = capsys.readouterr().out
    assert "Added 8 businesses and 8 listings" in out and "Added 0 businesses and 0 listings" in out

    r = await client.post("/auth/login", json={"email": "faisal@alnoorfoods.demo", "password": seed_marketplace.PASSWORD})
    assert r.status_code == 200, r.text
    me = (await client.get("/me")).json()
    assert me["status"] == "verified" and me["companyCode"].startswith("AE-")
    assert (await client.get("/wallet")).json()["balance"] == seed_marketplace.BUYER_CREDITS

    market = (await client.get("/public/products", params={"limit": 50})).json()
    assert market["total"] == 8
    rice = next(p for p in market["items"] if p["name"] == "Sona Masoori Raw Rice")
    assert rice["priceMin"] == "620.00" and rice["currency"] == "USD"

    seller = make_client()
    r = await seller.post("/auth/login", json={"email": "anil@kaveriagro.demo", "password": seed_marketplace.PASSWORD})
    assert r.status_code == 200
    mine = (await seller.get("/products")).json()
    assert {p["status"] for p in mine["items"]} == {"published"}
