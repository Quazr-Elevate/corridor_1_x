"""The eight payment terms as milestones (CX-110, A-083), and the checks a
contract's payment terms must pass before it is sent.

Pure functions: no database. A term and a contract value give the same
milestones every time, and their amounts add up to the value exactly (the
last part takes the rounding). The terms were proposed in the M5 design
review and approved there; they are to be checked against plan 10.1."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import BadRequest

#: Terms that let the buyer pay after documents or shipment, on credit: they
#: need a credit limit and credit insurance (plan 10.2).
CREDIT_TERMS = ("da", "open_account")
#: Terms with a tenor: days after the due event.
TENOR_TERMS = ("lc_usance", "da", "open_account")
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Spec:
    kind: str
    #: Share of the contract value in basis points (1 % = 100).
    share_bp: int
    due_event: str
    due_days: int
    gate: str


@dataclass(frozen=True)
class Planned:
    kind: str
    amount_minor: int
    due_event: str
    due_days: int
    gate: str


def specs(term: str, *, advance_pct: int | None = None, tenor_days: int | None = None) -> list[Spec]:
    """The buyer-side milestones of one term, as shares of the value."""
    tenor = tenor_days or 0
    table = {
        "advance": [Spec("advance", 10_000, "contract_effective", 0, "start_production")],
        "advance_balance_docs": [
            Spec("advance", (advance_pct or 0) * 100, "contract_effective", 0, "start_production"),
            Spec("balance", 10_000 - (advance_pct or 0) * 100, "documents", 0, "release_documents"),
        ],
        "cad": [Spec("cad", 10_000, "documents", 0, "release_documents")],
        "lc_sight": [Spec("lc_payment", 10_000, "documents", 0, "release_documents")],
        "lc_usance": [Spec("lc_payment", 10_000, "documents", tenor, "release_documents")],
        "da": [Spec("da_payment", 10_000, "documents", tenor, "release_documents")],
        "open_account": [Spec("open_account", 10_000, "shipment", tenor, "ship")],
        "escrow": [Spec("escrow_funding", 10_000, "contract_effective", 0, "start_production")],
    }
    if term not in table:
        raise BadRequest("Choose payment terms from the list.")
    return table[term]


def split(value_minor: int, parts: list[Spec]) -> list[Planned]:
    """Amounts for the shares; the last part takes what rounding leaves, so
    they always add up to ``value_minor``."""
    out, given = [], 0
    for i, s in enumerate(parts):
        amount = value_minor - given if i == len(parts) - 1 else value_minor * s.share_bp // 10_000
        given += amount
        out.append(Planned(s.kind, amount, s.due_event, s.due_days, s.gate))
    return out


def buyer_plan(term: str, value_minor: int, **params) -> list[Planned]:
    """What the buyer pays Corridor One X."""
    return split(value_minor, specs(term, **params))


def seller_plan(term: str, value_minor: int, retention_pct: int, **params) -> list[Planned]:
    """What Corridor One X pays the seller: every part opens a payout, and
    ``retention_pct`` of the value is held back from the last part until
    the buyer accepts the goods (A-083)."""
    planned = [Planned(p.kind, p.amount_minor, p.due_event, p.due_days, "pay_seller")
               for p in split(value_minor, specs(term, **params))]
    retention = value_minor * retention_pct // 100
    if retention:
        last = planned[-1]
        if last.amount_minor <= retention:
            raise BadRequest("The last payment to the seller is smaller than the retention. Change the payment terms.")
        planned[-1] = Planned(last.kind, last.amount_minor - retention, last.due_event, last.due_days, last.gate)
        planned.append(Planned("retention", retention, "acceptance", 0, "release_retention"))
    return planned


def validate(
    term: str, value_minor: int, *, outlay_cap_months: int, advance_pct: int | None = None,
    tenor_days: int | None = None, credit_limit_minor: int | None = None, credit_insurance_ref: str | None = None,
    buyer_side: bool,
) -> None:
    """Refuse payment terms that can't be run: an advance share out of range,
    a missing tenor or one past the outlay cap, and credit terms to a buyer
    without a credit limit covering the value and credit insurance."""
    specs(term, advance_pct=advance_pct, tenor_days=tenor_days)
    if term == "advance_balance_docs" and not (advance_pct and 1 <= advance_pct <= 99):
        raise BadRequest("Enter the advance as a percentage between 1 and 99.")
    if term in TENOR_TERMS:
        cap = outlay_cap_months * DAYS_PER_MONTH
        if not tenor_days or tenor_days < 1:
            raise BadRequest("Enter the credit period in days.")
        if tenor_days > cap:
            raise BadRequest(f"A {tenor_days}-day credit period is beyond the {outlay_cap_months}-month outlay cap ({cap} days).")
    if buyer_side and term in CREDIT_TERMS:
        if not credit_limit_minor or credit_limit_minor < value_minor:
            raise BadRequest("These terms give the buyer credit: set a credit limit that covers the contract value.")
        if not (credit_insurance_ref or "").strip():
            raise BadRequest("These terms give the buyer credit: record the credit insurance policy.")
