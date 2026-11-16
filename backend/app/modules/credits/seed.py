"""Starting prices and plans. Every value here is a placeholder until the
client sets it (plan 17.5, decision A-031); the rows carry ``is_placeholder``
so the console and the wallet can say so."""
from __future__ import annotations

import uuid

FREE_RFQ_ALLOWANCE = 10  # plan 17.2: free RFQs per verified company

_PRICES = (("RFQ_POST", 5), ("OFFER_UNLOCK", 2), ("RFQ_VIEW", 1), ("LISTING_BOOST", 10), ("AI_QUERY", 1), ("SAMPLE_FEE", 5))

# code, name, kind, credits, price in minor units, currency, period in days
_PLANS = (
    ("starter", "Starter", "plan", 50, 99900, "INR", 30),
    ("growth", "Growth", "plan", 200, 349900, "INR", 30),
    ("topup-25", "25 credits", "top_up", 25, 59900, "INR", None),
)


def default_price_rows() -> list[dict]:
    return [{"action": action, "credits": credits, "is_placeholder": True} for action, credits in _PRICES]


def default_plan_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "code": code, "name": name, "kind": kind, "credits": credits, "price_minor": price,
            "currency": currency, "period_days": period, "active": True, "is_placeholder": True, "sort_order": i,
        }
        for i, (code, name, kind, credits, price, currency, period) in enumerate(_PLANS)
    ]
