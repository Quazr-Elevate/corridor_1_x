"""The matcher's hard rules (CX-092, decision A-035; CX-175 and CX-176).
Pure functions: given an RFQ and a listing, say for each rule whether it is
met and why. A listing is proposed only when every rule is met; the desk
confirms before anyone is told."""
from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Any

from app.models.product import Product
from app.models.rfq import Rfq

_KG = {"MT": Decimal(1000), "quintal": Decimal(100), "kg": Decimal(1)}


def _in_kg(amount: Decimal | None, unit: str | None) -> Decimal | None:
    return amount * _KG[unit] if amount is not None and unit in _KG else None


def check_category(rfq: Rfq, listing: Product) -> dict[str, Any]:
    ok = listing.category == rfq.category
    return {"rule": "category", "ok": ok, "detail": f"Listing is {listing.category}; the request is for {rfq.category}."}


#: A month, for turning the days left into production months.
_MONTH_DAYS = Decimal(30)


def check_capacity(rfq: Rfq, listing: Product, today: date | None = None) -> dict[str, Any]:
    """The seller can supply the quantity: from stock, or from monthly
    capacity over the months left until the delivery window closes (at
    least one). One month's capacity against the whole order turned away
    sellers who could fill a long window (CX-175)."""
    need = _in_kg(rfq.quantity, rfq.unit)
    rate = _in_kg(listing.capacity_per_month, listing.capacity_unit)
    stock = _in_kg(listing.quantity, listing.unit)
    if need is None:
        return {"rule": "capacity", "ok": False, "detail": "The request has no quantity."}
    if rate is None and stock is None:
        return {"rule": "capacity", "ok": False, "detail": "The listing states no monthly capacity."}
    months = Decimal(1)
    if today is not None and rfq.delivery_to is not None:
        months = max(Decimal(1), (Decimal((rfq.delivery_to - today).days) / _MONTH_DAYS).quantize(Decimal("0.1"), ROUND_DOWN))
    can_make = rate * months if rate is not None else None
    from_stock = stock is not None and stock >= need
    ok = from_stock or (can_make is not None and can_make >= need)
    parts = []
    if rate is not None:
        parts.append(f"Capacity {_plain(listing.capacity_per_month)} {listing.capacity_unit} a month"
                     + (f" over {_plain(months)} months" if months != 1 else ""))
    if from_stock:
        parts.append(f"{_plain(listing.quantity)} {listing.unit} in stock")
    return {"rule": "capacity", "ok": ok, "detail": f"{' and '.join(parts)} against {_plain(rfq.quantity)} {rfq.unit} asked."}


def check_incoterms(rfq: Rfq, listing: Product) -> dict[str, Any]:
    """The listing offers at least one incoterm the buyer accepts."""
    wanted, offered = list(rfq.incoterms or []), list(listing.incoterms or [])
    both = [t for t in wanted if t in offered]
    if not offered:
        return {"rule": "incoterms", "ok": False, "detail": "The listing states no incoterm."}
    return {
        "rule": "incoterms", "ok": bool(both),
        "detail": f"Buyer accepts {', '.join(wanted) or 'none'}; listing offers {', '.join(offered)}.",
    }


def check_certificates(rfq: Rfq, on_file: dict[str, str], needed: dict[str, str]) -> dict[str, Any]:
    """Every document the buyer asked for is on the listing. ``on_file`` and
    ``needed`` map certificate type id to its name."""
    missing = [needed.get(t, "a document") for t in rfq.certificate_type_ids or [] if t not in on_file]
    if missing:
        return {"rule": "certificates", "ok": False, "detail": "Not on the listing: " + ", ".join(missing) + "."}
    asked = len(rfq.certificate_type_ids or [])
    return {"rule": "certificates", "ok": True, "detail": f"{asked} requested document(s) on the listing."}


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
    rfq: Rfq, listing: Product, listing_specs: list[dict[str, Any]], required: dict[str, str], today: date,
    *, on_file: dict[str, str] | None = None, needed: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Every hard rule against one listing, in a fixed order."""
    return [
        check_category(rfq, listing),
        check_capacity(rfq, listing, today),
        check_specs(rfq, listing_specs, required),
        check_lead_time(rfq, listing, today),
        check_incoterms(rfq, listing),
        check_certificates(rfq, on_file or {}, needed or {}),
    ]


def passes(reasons: list[dict[str, Any]]) -> bool:
    return all(r["ok"] for r in reasons)


def _plain(n: Decimal | None) -> str:
    return format(Decimal(n).normalize(), "f") if n is not None else "?"
