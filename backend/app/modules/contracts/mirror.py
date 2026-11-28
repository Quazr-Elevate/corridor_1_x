"""The mirror validator (M4 · S9, CX-105, A-081).

Corridor One X sells to the buyer on the sales contract and buys from the
seller on the purchase contract. Whatever it promises the buyer, the seller
must promise it; whatever it may have to pay the buyer, it must be able to
recover from the seller. Ten rules, each refused with a 422 that names the
field. Penalties are compared as money, never as rates (plan 9.1): two
contracts of different value at the same rate don't mirror.

The rules were proposed in the S9 design review and approved there; they are
to be checked against plan 9.1 when it is shared (A-081)."""
from __future__ import annotations

from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from app.core.errors import Unprocessable

#: (rule, terms that must be identical in both contracts)
IDENTICAL = (
    (1, ("product", "quality")),
    (2, ("quantity", "unit")),
    (4, ("incoterm", "port_of_loading", "destination_port")),
    (6, ("inspection_agency", "inspection_point")),
    (10, ("governing_law", "seat", "force_majeure")),
)


def _refuse(rule: int, field: str, message: str) -> None:
    raise Unprocessable(
        f"The contracts don't mirror (rule {rule}): {message}",
        code="contract.mirror", fields=[{"field": field, "message": message}],
    )


def penalty(value_minor: int, pct: str | Decimal, *, rounding: str) -> int:
    """A penalty in minor units: what Corridor One X recovers rounds down,
    what it pays out rounds up."""
    return int((Decimal(value_minor) * Decimal(pct) / 100).to_integral_value(rounding=rounding))


def check(sales: dict, purchase: dict, *, purchase_to_sales_rate: Decimal) -> None:
    """Refuse the pair on the first rule it breaks. ``purchase_to_sales_rate``
    converts the purchase currency into the sales currency (the cost sheet's
    stored rate), so penalties are compared in one currency."""
    for rule, terms in IDENTICAL:
        for term in terms:
            if sales.get(term) != purchase.get(term):
                _refuse(rule, f"purchase.{term}", f"{term.replace('_', ' ')} must be the same in both contracts.")

    if Decimal(purchase["tolerance_pct"]) > Decimal(sales["tolerance_pct"]):
        _refuse(3, "purchase.tolerance_pct",
                "the seller's quantity tolerance can't be wider than the buyer's.")

    if date.fromisoformat(purchase["shipment_from"]) < date.fromisoformat(sales["shipment_from"]) or \
            date.fromisoformat(purchase["shipment_to"]) > date.fromisoformat(sales["shipment_to"]):
        _refuse(5, "purchase.shipment_to",
                "the seller's shipment window must fall inside the buyer's.")

    for rule, term in ((7, "late_penalty_pct"), (8, "quality_penalty_pct")):
        payout = penalty(sales["value_minor"], sales[term], rounding=ROUND_CEILING)
        recovery_in_purchase = penalty(purchase["value_minor"], purchase[term], rounding=ROUND_FLOOR)
        recovery = int((Decimal(recovery_in_purchase) * purchase_to_sales_rate).to_integral_value(rounding=ROUND_FLOOR))
        if recovery < payout:
            what = "late-delivery" if rule == 7 else "quality"
            _refuse(rule, f"purchase.{term}",
                    f"the {what} penalty recoverable from the seller ({recovery / 100:,.2f}) is less than the one "
                    f"payable to the buyer ({payout / 100:,.2f}), in {sales['currency']}.")

    if int(purchase["claim_window_days"]) < int(sales["claim_window_days"]):
        _refuse(9, "purchase.claim_window_days",
                "the claim window against the seller must close no earlier than the buyer's.")
