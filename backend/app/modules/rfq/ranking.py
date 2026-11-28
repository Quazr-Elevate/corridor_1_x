"""Ranking proposed sellers (CX-177, A-082).

The hard rules (``matching``) decide who may be proposed; this decides the
order, out of 100:

* **Optional specifications, 40.** Of the limits the buyer set on
  parameters the category doesn't require, the share the listing states and
  meets. None set: full marks, as no listing can do better.
* **Price, 40.** The listing's lowest price against the buyer's highest
  target, in one currency: at or under it, full marks; falling to nothing at
  25 % over. No target, no listing price or no rate: half marks.
* **Response history, 20.** Of the requests this seller was sent in the last
  year, the share it quoted on. No history yet: half marks, so new sellers
  aren't buried.

Each part is kept with a sentence the desk reads next to the score."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.product import Product
from app.models.rfq import Rfq
from app.modules.fx.service import LatestRates, convert
from app.modules.rfq.matching import within

SPEC_WEIGHT, PRICE_WEIGHT, RESPONSE_WEIGHT = 40, 40, 20
#: How far over the buyer's target a price may be before it scores nothing.
PRICE_TOLERANCE = Decimal("0.25")


@dataclass(frozen=True)
class Score:
    total: int
    parts: dict[str, Any]


def _spec_fit(rfq: Rfq, listing_specs: list[dict[str, Any]], required: dict[str, str]) -> tuple[Decimal, str]:
    optional = [s for s in rfq.specs or [] if s["parameter_id"] not in required]
    if not optional:
        return Decimal(1), "No optional specifications asked for."
    stated = {s["parameter_id"]: s for s in listing_specs}
    met = sum(
        1 for s in optional
        if s["parameter_id"] in stated and within(stated[s["parameter_id"]]["value"], s["value"], s["operator"])
    )
    return Decimal(met) / len(optional), f"Meets {met} of {len(optional)} optional specification(s)."


def _price_fit(rfq: Rfq, listing: Product, rates: LatestRates) -> tuple[Decimal, str]:
    ceiling = rfq.target_price_max or rfq.target_price_min
    if not ceiling or not rfq.currency or listing.price_per_unit is None or listing.unit != rfq.unit:
        return Decimal("0.5"), "No comparable target price."
    target = convert(Decimal(ceiling) / 100, rfq.currency, listing.currency, rates)
    if target is None or target <= 0:
        return Decimal("0.5"), "No exchange rate to compare the price."
    over = (Decimal(listing.price_per_unit) - target) / target
    if over <= 0:
        return Decimal(1), "Listed price is within the buyer's target."
    fit = max(Decimal(0), 1 - over / PRICE_TOLERANCE)
    return fit, f"Listed price is {over * 100:.0f} % over the buyer's target."


def _response_fit(sent: int, quoted: int) -> tuple[Decimal, str]:
    if sent == 0:
        return Decimal("0.5"), "No requests sent to this seller in the last year."
    return Decimal(quoted) / sent, f"Quoted on {quoted} of {sent} request(s) in the last year."


def score(
    rfq: Rfq, listing: Product, listing_specs: list[dict[str, Any]], required: dict[str, str], rates: LatestRates,
    *, sent: int, quoted: int,
) -> Score:
    parts = {}
    total = Decimal(0)
    for name, weight, (fit, why) in (
        ("specs", SPEC_WEIGHT, _spec_fit(rfq, listing_specs, required)),
        ("price", PRICE_WEIGHT, _price_fit(rfq, listing, rates)),
        ("response", RESPONSE_WEIGHT, _response_fit(sent, quoted)),
    ):
        points = fit * weight
        total += points
        parts[name] = {"points": round(float(points), 1), "of": weight, "detail": why}
    return Score(total=int(total.to_integral_value()), parts=parts)
