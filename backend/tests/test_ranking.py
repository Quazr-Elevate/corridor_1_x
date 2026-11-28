"""Ranking proposed sellers (CX-177) and cost lines in their own currency
(CX-185), both A-082."""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from test_quotes import SHEET, TODAY, _quoted, parties  # noqa: F401  (fixture)
from test_rfq import _submitted

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models import ExchangeRate, RfqMatch
from app.modules.fx.service import LatestRates
from app.modules.rfq.ranking import score

RATES = LatestRates(rates={"USD": Decimal(1), "INR": Decimal(80), "AED": Decimal("3.6725")})


def _rfq(**over):
    base = dict(specs=[], target_price_max=None, target_price_min=None, currency=None, unit="MT")
    return SimpleNamespace(**{**base, **over})


def _listing(**over):
    base = dict(price_per_unit=None, currency="INR", unit="MT")
    return SimpleNamespace(**{**base, **over})


# ── The score ────────────────────────────────────────────────────────


def test_price_scores_full_at_target_and_nothing_at_25_percent_over():
    rfq = _rfq(target_price_max=7_200_000, currency="INR")  # ₹72,000.00
    at = score(rfq, _listing(price_per_unit=Decimal("72000")), [], {}, RATES, sent=0, quoted=0)
    over = score(rfq, _listing(price_per_unit=Decimal("81000")), [], {}, RATES, sent=0, quoted=0)  # 12.5 % over
    far = score(rfq, _listing(price_per_unit=Decimal("90000")), [], {}, RATES, sent=0, quoted=0)  # 25 % over
    assert (at.parts["price"]["points"], over.parts["price"]["points"], far.parts["price"]["points"]) == (40.0, 20.0, 0.0)
    # Compared in one currency: a USD target against an INR price.
    usd = _rfq(target_price_max=90_000, currency="USD")  # $900 = ₹72,000 at 80
    assert score(usd, _listing(price_per_unit=Decimal("72000")), [], {}, RATES, sent=0, quoted=0).parts["price"]["points"] == 40.0


def test_the_same_currency_compares_without_any_stored_rate():
    no_rates = LatestRates(rates={"USD": Decimal(1)})
    rfq = _rfq(target_price_max=7_200_000, currency="INR")
    s = score(rfq, _listing(price_per_unit=Decimal("72000")), [], {}, no_rates, sent=0, quoted=0)
    assert s.parts["price"]["points"] == 40.0


def test_unknowns_score_half_so_nobody_is_buried():
    s = score(_rfq(), _listing(), [], {}, RATES, sent=0, quoted=0)
    assert s.parts["price"]["points"] == 20.0 and s.parts["response"]["points"] == 10.0
    assert s.parts["specs"]["points"] == 40.0  # no optional specs asked: nothing to lose
    assert s.total == 70


def test_optional_specs_count_only_what_the_category_doesnt_require():
    rfq = _rfq(specs=[
        {"parameter_id": "moist", "value": "12", "operator": "MAX"},  # required: the hard rules' business
        {"parameter_id": "len", "value": "7", "operator": "MIN"},
        {"parameter_id": "broken", "value": "5", "operator": "MAX"},
    ])
    stated = [{"parameter_id": "len", "value": "8.3"}, {"parameter_id": "broken", "value": "9"}]
    s = score(rfq, _listing(), stated, {"moist": "Moisture"}, RATES, sent=4, quoted=3)
    assert s.parts["specs"]["points"] == 20.0 and "1 of 2" in s.parts["specs"]["detail"]
    assert s.parts["response"]["points"] == 15.0 and "3 of 4" in s.parts["response"]["detail"]


# ── In the queue ─────────────────────────────────────────────────────


async def test_proposals_carry_their_score_and_a_seller_that_quotes_scores_higher(parties, admin_client):
    p = parties
    await _quoted(p["seller_client"], p["buyer_client"], admin_client, p["seller"])  # sent 1, quoted 1
    rfq = await _submitted(p["buyer_client"])
    detail = (await admin_client.get(f"/admin/rfqs/{rfq['id']}")).json()
    match = detail["matches"][0]
    assert 0 <= match["score"] <= 100
    assert match["scoreParts"]["response"] == {"points": 20.0, "of": 20, "detail": "Quoted on 1 of 1 request(s) in the last year."}
    async with SessionLocal() as db:
        assert (await db.scalar(select(RfqMatch.score).where(RfqMatch.id == uuid.UUID(match["id"])))) == match["score"]


# ── Cost lines in their own currency (CX-185) ────────────────────────


async def test_a_usd_freight_line_is_converted_once_rounded_up_and_kept(parties, admin_client):
    async with SessionLocal() as db:
        db.add(ExchangeRate(base="USD", quote="INR", rate=Decimal("83.3333"), as_of=TODAY, source="test", fetched_at=utcnow()))
        await db.commit()
    _, quote = await _quoted(parties["seller_client"], parties["buyer_client"], admin_client, parties["seller"])
    url = f"/admin/quotes/{quote['id']}/cost-sheet"
    # $30.00 of ocean freight per MT, in an INR sheet.
    r = await admin_client.put(url, json={**SHEET, "oceanFreightMinor": 3000, "oceanFreightCurrency": "USD"})
    assert r.status_code == 200, r.text
    sheet = r.json()
    # 3000 × 83.3333 = 249,999.9 → 250,000 (up: costs never round against the margin).
    assert sheet["oceanFreightMinor"] == 250_000
    entry = sheet["lineEntries"][0]
    assert (entry["line"], entry["amountMinor"], entry["currency"], Decimal(entry["rate"])) == (
        "ocean_freight", 3000, "USD", Decimal("83.3333"),
    )
    assert entry["asOf"] == TODAY.isoformat() and sheet["fxAsOf"] == TODAY.isoformat()
    # Lines in the quote's own currency aren't listed; the total uses the converted
    # amount (the fixture's other costs are ₹5,000, ocean freight ₹2,500 of them).
    assert len(sheet["lineEntries"]) == 1 and sheet["totalCostMinor"] == 7_700_000

    # A currency with no stored rate is refused, not guessed.
    r = await admin_client.put(url, json={**SHEET, "insuranceMinor": 100, "insuranceCurrency": "EUR"})
    assert r.status_code == 409 and "EUR" in r.json()["detail"]

