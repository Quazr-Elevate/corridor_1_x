"""Exchange rates (docs/04_data_model.md → "Exchange rates"): providers,
fallback chain, AED peg, sanity bounds, price_usd upkeep, market filter in
any supported currency, display currency, DB constraints.

Never touches the network: HTTP providers run on httpx.MockTransport with
real-shaped payloads; the app uses the static provider (conftest)."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from conftest import png_bytes, set_status, signup_and_login
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.integrations.fx import (
    FawazProvider,
    FrankfurterProvider,
    FxChain,
    FxConfig,
    FxError,
    FxProvider,
    FxRates,
    StaticProvider,
    parse_fawaz,
    parse_frankfurter,
)
from app.models import Business, ExchangeRate, Product, User
from app.models.business import BusinessStatus
from app.modules.fx import service as fx
from app.modules.fx.scheduler import FxRefresher

TODAY = utcnow().date()

# Real response shapes (captured 2026-10-17).
FRANKFURTER_PAYLOAD = [
    {"date": "2026-10-17", "base": "USD", "quote": "AED", "rate": 3.6725},
    {"date": "2026-10-17", "base": "USD", "quote": "INR", "rate": 94.94},
]
FAWAZ_PAYLOAD = {
    "date": "2026-10-17",
    "usd": {"1inch": 10.69680634, "aed": 3.6725, "afn": 65.34770057, "inr": 94.97110529, "usd": 1},
}

CFG = FxConfig(providers=("static",), max_attempts=1, http_timeout_sec=2)


class FakeProvider(FxProvider):
    def __init__(self, name: str, rates: dict[str, Decimal] | None = None, *, fail: bool = False) -> None:
        super().__init__(CFG)
        self.name = name
        self._rates = rates or {}
        self._fail = fail
        self.calls: list[list[str]] = []

    async def fetch_usd_rates(self, currencies: Iterable[str]) -> FxRates:
        wanted = list(currencies)
        self.calls.append(wanted)
        if self._fail:
            raise FxError(f"{self.name} down")
        return FxRates(as_of=TODAY, rates={c: r for c, r in self._rates.items() if c in wanted}, source=self.name)


# ── Providers ─────────────────────────────────────────────────────────


def test_parse_real_shaped_payloads():
    f = parse_frankfurter(FRANKFURTER_PAYLOAD, ["INR", "AED", "USD"])
    assert f.rates == {"INR": Decimal("94.94"), "AED": Decimal("3.6725")}
    assert f.as_of == date(2026, 10, 17) and f.source == "frankfurter"
    w = parse_fawaz(FAWAZ_PAYLOAD, ["inr", "AED"])
    assert w.rates == {"INR": Decimal("94.97110529"), "AED": Decimal("3.6725")}
    assert w.as_of == date(2026, 10, 17) and w.source == "fawazahmed0"
    with pytest.raises(FxError):
        parse_frankfurter({"rates": {}}, ["INR"])
    with pytest.raises(FxError):
        parse_frankfurter([{"date": "2026-10-17", "base": "USD", "quote": "INR", "rate": -1}], ["INR"])
    with pytest.raises(FxError):
        parse_fawaz({"date": "2026-10-17", "eur": {}}, ["INR"])


async def test_frankfurter_provider_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=FRANKFURTER_PAYLOAD)

    p = FrankfurterProvider(CFG, transport=httpx.MockTransport(handler))
    rates = await p.fetch_usd_rates(["INR", "AED", "USD"])
    assert seen["url"].startswith("https://api.frankfurter.dev/v2/rates?")
    assert "base=USD" in seen["url"] and "quotes=INR%2CAED" in seen["url"]
    assert rates.rates["INR"] == Decimal("94.94")


async def test_fawaz_falls_back_to_cloudflare_mirror():
    hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "cdn.jsdelivr.net":
            return httpx.Response(503)
        return httpx.Response(200, json=FAWAZ_PAYLOAD)

    p = FawazProvider(CFG, transport=httpx.MockTransport(handler))
    rates = await p.fetch_usd_rates(["INR"])
    assert hosts == ["cdn.jsdelivr.net", "latest.currency-api.pages.dev"]
    assert rates.rates == {"INR": Decimal("94.97110529")}


async def test_static_provider_is_offline():
    rates = await StaticProvider(CFG).fetch_usd_rates(["INR", "AED", "USD"])
    assert rates.rates == {"INR": Decimal("95"), "AED": Decimal("3.6725")} and rates.as_of == TODAY


# ── Chain ─────────────────────────────────────────────────────────────


async def test_chain_falls_back_per_currency():
    down = FakeProvider("frankfurter", fail=True)
    partial = FakeProvider("fawazahmed0", {"INR": Decimal("94.5")})
    last = FakeProvider("static", {"INR": Decimal("1"), "AED": Decimal("3.67")})
    quotes = await FxChain([down, partial, last]).fetch(["INR", "AED", "USD"])
    assert {c: (q.rate, q.source) for c, q in quotes.items()} == {
        "INR": (Decimal("94.5"), "fawazahmed0"),
        "AED": (Decimal("3.67"), "static"),
    }
    assert last.calls == [["AED"]]  # only asked for what was still missing


async def test_chain_aed_peg_fallback():
    quotes = await FxChain([FakeProvider("frankfurter", fail=True)]).fetch(["INR", "AED"], today=TODAY)
    assert "INR" not in quotes  # caller keeps its last stored rate
    assert quotes["AED"].rate == Decimal("3.6725") and quotes["AED"].source == "pegged"


# ── refresh / sanity / price_usd ─────────────────────────────────────


async def _rate_rows(quote: str) -> list[ExchangeRate]:
    async with SessionLocal() as db:
        return list(await db.scalars(select(ExchangeRate).where(ExchangeRate.quote == quote)))


async def _store(quote: str, rate: str, as_of: date, source: str = "manual") -> None:
    async with SessionLocal() as db:
        db.add(ExchangeRate(base="USD", quote=quote, rate=Decimal(rate), as_of=as_of, source=source, fetched_at=utcnow()))
        await db.commit()


async def test_sanity_bound_rejects_jump_and_keeps_last():
    yesterday = TODAY - timedelta(days=1)
    await _store("INR", "95", yesterday, "frankfurter")
    await _store("AED", "3.6725", yesterday, "frankfurter")
    chain = FxChain([FakeProvider("frankfurter", {"INR": Decimal("150"), "AED": Decimal("3.6726")})])
    async with SessionLocal() as db:
        result = await fx.refresh_rates(db, chain)
        latest = await fx.get_latest_rates(db)
    assert result.rejected == ["INR"] and [q.quote for q in result.stored] == ["AED"]
    assert latest.rate("INR") == Decimal("95") and latest.as_of_by["INR"] == yesterday  # last kept
    assert latest.rate("AED") == Decimal("3.6726") and latest.as_of_by["AED"] == TODAY

    # Non-positive rates never get stored either.
    chain = FxChain([FakeProvider("frankfurter", {"INR": Decimal("0")})])
    async with SessionLocal() as db:
        result = await fx.refresh_rates(db, chain)
    assert result.rejected == ["INR"]
    assert len(await _rate_rows("INR")) == 1


async def test_refresh_upserts_one_row_per_day():
    async with SessionLocal() as db:
        await fx.refresh_rates(db, FxChain([FakeProvider("frankfurter", {"INR": Decimal("94.94")})]))
        await fx.refresh_rates(db, FxChain([FakeProvider("fawazahmed0", {"INR": Decimal("94.97")})]))
    rows = await _rate_rows("INR")
    assert len(rows) == 1 and rows[0].rate == Decimal("94.97") and rows[0].source == "fawazahmed0"
    assert len(await _rate_rows("AED")) == 1  # peg filled in


async def _photo(c) -> str:
    r = await c.post("/products/upload-photo", files={"file": ("p.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["url"]


async def _list(c, name: str, price: str | None, currency: str, category: str = "Rice") -> dict:
    body = {"name": name, "category": category, "quantity": "100", "currency": currency, "photos": [await _photo(c)]}
    if price is not None:
        body["pricePerUnit"] = price
    r = await c.post("/products", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _verified_seller(c, email: str) -> dict:
    who = await signup_and_login(c, email)
    await set_status(who["userId"], BusinessStatus.verified)
    return who


async def _seed_rates(inr: str = "95", aed: str = "3.6725") -> None:
    await _store("INR", inr, TODAY)
    await _store("AED", aed, TODAY, "pegged")


async def test_product_create_sets_price_usd(client):
    await _seed_rates()
    await signup_and_login(client, "px@kaverifoods.in")
    inr = await _list(client, "INR lot", "9500", "INR")
    aed = await _list(client, "AED lot", "520", "AED")
    usd = await _list(client, "USD lot", "480", "USD")
    unpriced = await _list(client, "No price", None, "INR")
    assert (inr["priceUsd"], inr["priceUsdAsOf"]) == ("100.00", TODAY.isoformat())
    assert aed["currency"] == "AED" and aed["priceUsd"] == "141.59"  # 520 / 3.6725
    assert usd["priceUsd"] == "480.00"
    assert unpriced["priceUsd"] is None and unpriced["priceUsdAsOf"] is None
    # Only supported currencies can be listed in.
    r = await client.post(
        "/products", json={"name": "EUR lot", "category": "Rice", "currency": "EUR", "photos": [await _photo(client)]}
    )
    assert r.status_code == 400 and "INR, AED, USD" in r.json()["detail"]


async def test_refresh_recomputes_price_usd(client):
    await _seed_rates()
    await signup_and_login(client, "rc@kaverifoods.in")
    inr = await _list(client, "INR lot", "9500", "INR")
    aed = await _list(client, "AED lot", "367.25", "AED")
    gone = await _list(client, "Deleted lot", "9500", "INR")
    assert (await client.delete(f"/products/{gone['id']}")).status_code == 204
    tomorrow = TODAY + timedelta(days=1)

    class Tomorrow(FakeProvider):
        async def fetch_usd_rates(self, currencies):
            r = await super().fetch_usd_rates(currencies)
            return FxRates(as_of=tomorrow, rates=r.rates, source=r.source)

    async with SessionLocal() as db:
        result = await fx.refresh_rates(db, FxChain([Tomorrow("frankfurter", {"INR": Decimal("100"), "AED": Decimal("3.6725")})]))
        assert result.products_updated == 2
        rows = {p.name: p for p in await db.scalars(select(Product))}
    assert rows["INR lot"].price_usd == Decimal("95.00") and rows["INR lot"].price_usd_as_of == tomorrow
    assert rows["AED lot"].price_usd == Decimal("100.00")
    assert rows["Deleted lot"].price_usd == Decimal("100.00")  # deleted rows are left alone
    assert rows["INR lot"].price_per_unit == Decimal("9500")  # seller's price never changes
    assert inr["id"] and aed["id"]


async def test_market_price_filter_in_any_currency(client, make_client):
    await _seed_rates()  # 1 USD = 95 INR = 3.6725 AED
    await _verified_seller(client, "mk@kaverifoods.in")
    await _list(client, "INR 9500", "9500", "INR")  # $100.00
    await _list(client, "AED 520", "520", "AED")  # $141.59 (≈ ₹13,451)
    await _list(client, "USD 480", "480", "USD")  # $480.00
    await _list(client, "Unpriced", None, "INR")
    anon = make_client()

    async def names(**params) -> set[str]:
        r = await anon.get("/public/products", params=params)
        assert r.status_code == 200, r.text
        return {i["name"] for i in r.json()["items"]}

    # USD (and the backward-compatible default when priceCurrency is absent).
    assert await names(minPrice="100", maxPrice="150", priceCurrency="USD") == {"INR 9500", "AED 520"}
    assert await names(minPrice="100", maxPrice="150") == {"INR 9500", "AED 520"}
    assert await names(minPrice="200") == {"USD 480"}
    # INR: bounds equal to a listing's own price still match it.
    assert await names(minPrice="9500", maxPrice="9500", priceCurrency="INR") == {"INR 9500"}
    assert await names(minPrice="10000", maxPrice="20000", priceCurrency="INR") == {"AED 520"}
    assert await names(maxPrice="13000", priceCurrency="inr") == {"INR 9500"}
    # AED
    assert await names(minPrice="520", maxPrice="520", priceCurrency="AED") == {"AED 520"}
    assert await names(minPrice="1000", priceCurrency="AED") == {"USD 480"}
    assert len(await names()) == 4  # no bounds → unpriced lots too
    r = await anon.get("/public/products", params={"minPrice": "1", "priceCurrency": "EUR"})
    assert r.status_code == 400

    card = (await anon.get("/public/products", params={"q": "AED"})).json()["items"][0]
    assert (card["priceUsd"], card["priceUsdAsOf"], card["currency"]) == ("141.59", TODAY.isoformat(), "AED")
    detail = (await anon.get(f"/public/products/{card['id']}")).json()
    assert detail["priceUsd"] == "141.59"

    facets = (await anon.get("/public/catalog/facets")).json()
    assert (facets["priceMin"], facets["priceMax"]) == ("100.00", "480.00")
    assert facets["priceCurrency"] == "USD" and facets["fxAsOf"] == TODAY.isoformat()


async def test_price_filter_without_rates_is_503(client, make_client):
    await _verified_seller(client, "nr@kaverifoods.in")
    await _list(client, "INR lot", "9500", "INR")
    anon = make_client()
    assert (await anon.get("/public/products", params={"minPrice": "1", "priceCurrency": "INR"})).status_code == 503
    # USD needs no rate.
    assert (await anon.get("/public/products", params={"minPrice": "1"})).status_code == 200


async def test_public_fx_rates(make_client):
    anon = make_client()
    empty = (await anon.get("/public/fx/rates")).json()
    assert empty == {"base": "USD", "asOf": None, "rates": {"USD": 1.0}, "source": None}
    await _seed_rates()
    body = (await anon.get("/public/fx/rates")).json()
    assert body["base"] == "USD" and body["asOf"] == TODAY.isoformat()
    assert body["rates"] == {"USD": 1.0, "INR": 95.0, "AED": 3.6725}
    assert body["source"] == "manual,pegged"


async def test_convert_helper():
    rates = fx.LatestRates(rates={"USD": Decimal(1), "INR": Decimal("95"), "AED": Decimal("3.6725")})
    assert fx.convert(Decimal("520"), "AED", "INR", rates).quantize(Decimal("1")) == Decimal("13451")
    assert fx.convert(Decimal("1"), "USD", "USD", rates) == 1
    assert fx.convert(Decimal("1"), "EUR", "USD", rates) is None


# ── Display currency ─────────────────────────────────────────────────


async def test_display_currency_default_update_and_validation(client):
    await signup_and_login(client, "dc@kaverifoods.in")
    me = (await client.get("/me")).json()
    assert me["displayCurrency"] == "INR"  # business country defaults to IN
    r = await client.patch("/me", json={"displayCurrency": "aed"})
    assert r.status_code == 200, r.text
    assert r.json()["displayCurrency"] == "AED"
    assert (await client.get("/me")).json()["displayCurrency"] == "AED"
    r = await client.patch("/me", json={"displayCurrency": "EUR"})
    assert r.status_code == 400 and "INR, AED, USD" in r.json()["detail"]
    assert (await client.patch("/me", json={"displayCurrency": "EURO"})).status_code == 422
    assert (await client.patch("/me", json={})).json()["displayCurrency"] == "AED"  # untouched


async def test_display_currency_default_follows_business_country():
    """Comes from ``countries.default_currency`` (SA is added here: USD)."""
    from app.models.country import Country
    from app.modules.verification.seed import country_row

    async with SessionLocal() as db:
        db.add(Country(**country_row("SA")))
        await db.commit()
        for country, expected in (("AE", "AED"), ("IN", "INR"), ("SA", "USD")):
            u = User(
                business=Business(country=country, verification_status=BusinessStatus.draft),
                email=f"{country.lower()}-{uuid.uuid4().hex[:6]}@acme.in",
                password_hash="x",
                email_verified_at=utcnow(),
                full_name="Test",
            )
            db.add(u)
            await db.commit()
            assert u.display_currency == expected


# ── Constraints ──────────────────────────────────────────────────────


async def _insert(table, **values):
    async with SessionLocal() as db:
        await db.execute(insert(table), [values])
        await db.commit()


def _rate(**over) -> dict:
    return {"id": uuid.uuid4(), "base": "USD", "quote": "INR", "rate": Decimal("95"), "as_of": TODAY,
            "source": "manual"} | over


@pytest.mark.parametrize(
    ("over", "name"),
    [
        ({"rate": Decimal("0")}, "ck_exchange_rates_rate_positive"),
        ({"rate": Decimal("-1")}, "ck_exchange_rates_rate_positive"),
        ({"quote": "RUPEE"}, "ck_exchange_rates_codes"),
        ({"base": "US"}, "ck_exchange_rates_codes"),
    ],
)
async def test_exchange_rate_checks(over, name):
    with pytest.raises(IntegrityError, match=name):
        await _insert(ExchangeRate.__table__, **_rate(**over))


async def test_exchange_rate_unique_per_day():
    await _insert(ExchangeRate.__table__, **_rate())
    await _insert(ExchangeRate.__table__, **_rate(as_of=TODAY - timedelta(days=1)))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        await _insert(ExchangeRate.__table__, **_rate(rate=Decimal("96")))


async def test_price_usd_and_display_currency_checks(client):
    who = await signup_and_login(client, "ck@kaverifoods.in")
    pid = (await _list(client, "Lot", "100", "INR"))["id"]
    async with SessionLocal() as db:
        with pytest.raises(IntegrityError, match="ck_products_price_usd"):
            await db.execute(update(Product).where(Product.id == uuid.UUID(pid)).values(price_usd=Decimal("-0.01")))
            await db.commit()
    async with SessionLocal() as db:
        with pytest.raises(IntegrityError, match="ck_users_display_currency"):
            await db.execute(update(User).where(User.id == uuid.UUID(who["userId"])).values(display_currency="EUR"))
            await db.commit()


# ── Background refresh ───────────────────────────────────────────────


async def test_refresher_runs_on_start_when_missing_and_stops_cleanly():
    async with SessionLocal() as db:
        assert await fx.refresh_due(db)
    refresher = FxRefresher(interval_hours=24)
    refresher.start()
    for _ in range(100):
        if await _rate_rows("INR"):
            break
        await asyncio.sleep(0.02)
    await refresher.stop()
    [row] = await _rate_rows("INR")
    assert row.source == "static" and row.rate == Decimal("95")
    async with SessionLocal() as db:
        assert not await fx.refresh_due(db)
    await _store("INR", "95", TODAY + timedelta(days=1), "manual")  # bootstrap placeholder → due again
    async with SessionLocal() as db:
        assert await fx.refresh_due(db)
