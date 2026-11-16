"""The matcher's hard rules (CX-092, decision A-035). Pure functions: given
an RFQ and a listing, say for each rule whether it is met and why. A listing
is proposed only when every rule is met; the desk confirms before anyone is
told."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.product import Product
from app.models.rfq import Rfq

_KG = {"MT": Decimal(1000), "quintal": Decimal(100), "kg": Decimal(1)}


def _in_kg(amount: Decimal | None, unit: str | None) -> Decimal | None:
    return amount * _KG[unit] if amount is not None and unit in _KG else None


def check_category(rfq: Rfq, listing: Product) -> dict[str, Any]:
    ok = listing.category == rfq.category
    return {"rule": "category", "ok": ok, "detail": f"Listing is {listing.category}; the request is for {rfq.category}."}


def check_capacity(rfq: Rfq, listing: Product) -> dict[str, Any]:
    """Monthly capacity must cover the quantity asked for."""
    need = _in_kg(rfq.quantity, rfq.unit)
    have = _in_kg(listing.capacity_per_month, listing.capacity_unit)
    if need is None:
        return {"rule": "capacity", "ok": False, "detail": "The request has no quantity."}
    if have is None:
        return {"rule": "capacity", "ok": False, "detail": "The listing states no monthly capacity."}
    return {
        "rule": "capacity", "ok": have >= need,
        "detail": f"Capacity {_plain(listing.capacity_per_month)} {listing.capacity_unit} a month against "
                  f"{_plain(rfq.quantity)} {rfq.unit} asked.",
    }


def check_lead_time(rfq: Rfq, listing: Product, today: date) -> dict[str, Any]:
    """The goods must be ready before the delivery window closes."""
    if rfq.delivery_to is None:
        return {"rule": "lead_time", "ok": False, "detail": "The request has no delivery date."}
    if listing.lead_time_days is None:
        return {"rule": "lead_time", "ok": False, "detail": "The listing states no lead time."}
    days = (rfq.delivery_to - today).days
    return {
        "rule": "lead_time", "ok": listing.lead_time_days <= days,
        "detail": f"Lead time {listing.lead_time_days} days; {max(days, 0)} days until the window closes.",
    }


def check_specs(rfq: Rfq, listing_specs: list[dict[str, Any]], required: dict[str, str]) -> dict[str, Any]:
    """Every required parameter the buyer set a limit on must be stated by
    the listing and fall inside the limit. ``required`` maps parameter id to
    its name."""
    stated = {s["parameter_id"]: s for s in listing_specs}
    problems = []
    checked = 0
    for limit in rfq.specs or []:
        name = required.get(limit["parameter_id"])
        if name is None:
            continue  # an optional parameter only ranks; it never excludes
        checked += 1
        mine = stated.get(limit["parameter_id"])
        if mine is None:
            problems.append(f"{name}: not stated")
        elif not within(mine["value"], limit["value"], limit["operator"]):
            problems.append(f"{name}: {mine['value']} against {limit['operator'].lower()} {limit['value']}")
    if problems:
        return {"rule": "specs", "ok": False, "detail": "; ".join(problems)}
    return {"rule": "specs", "ok": True, "detail": f"{checked} required specification(s) within the buyer's limits."}


def within(value: str, limit: str, operator: str) -> bool:
    """Is the seller's ``value`` inside the buyer's ``limit``? Numbers compare
    as numbers; text must match, ignoring case and spacing."""
    try:
        v, l = Decimal(value), Decimal(limit)
    except (InvalidOperation, TypeError):
        return operator == "EQ" and " ".join(str(value).split()).lower() == " ".join(str(limit).split()).lower()
    if operator == "MAX":
        return v <= l
    if operator == "MIN":
        return v >= l
    return v == l


def evaluate(
    rfq: Rfq, listing: Product, listing_specs: list[dict[str, Any]], required: dict[str, str], today: date
) -> list[dict[str, Any]]:
    """Every hard rule against one listing, in a fixed order."""
    return [
        check_category(rfq, listing),
        check_capacity(rfq, listing),
        check_specs(rfq, listing_specs, required),
        check_lead_time(rfq, listing, today),
    ]


def passes(reasons: list[dict[str, Any]]) -> bool:
    return all(r["ok"] for r in reasons)


def _plain(n: Decimal | None) -> str:
    return format(Decimal(n).normalize(), "f") if n is not None else "?"
