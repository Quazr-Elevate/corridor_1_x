"""The ten mirror rules (CX-105, A-081) as a pure function: each refusal
names its field, and penalties compare as money, not rates."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import Unprocessable
from app.modules.contracts.mirror import check

BASE = {
    "product": "Sona Masoori Raw Rice", "quality": "Moisture: at most 12 %", "quantity": "500", "unit": "MT",
    "incoterm": "FOB", "port_of_loading": "Chennai", "destination_port": "Jebel Ali",
    "inspection_agency": "SGS", "inspection_point": "Port of loading", "governing_law": "England and Wales",
    "seat": "London (LCIA)", "force_majeure": "GAFTA 125", "tolerance_pct": "5",
    "shipment_from": "2027-02-01", "shipment_to": "2027-03-15", "late_penalty_pct": "2",
    "quality_penalty_pct": "1", "claim_window_days": 30, "currency": "INR",
}
# A-081's case: payout 2 % of ₹1,08,00,000 = ₹2,16,000; recovery 2.5 % of ₹92,88,000 = ₹2,32,200.
SALES = {**BASE, "value_minor": 10_800_000_00}
PURCHASE = {**BASE, "value_minor": 9_288_000_00, "late_penalty_pct": "2.5", "quality_penalty_pct": "1.2"}


def _refused(sales: dict, purchase: dict, rate: Decimal = Decimal(1)) -> dict:
    with pytest.raises(Unprocessable) as e:
        check(sales, purchase, purchase_to_sales_rate=rate)
    assert e.value.status_code == 422 and e.value.code == "contract.mirror"
    return e.value.fields[0]


def test_the_penalty_case_passes_on_amounts():
    check(SALES, PURCHASE, purchase_to_sales_rate=Decimal(1))  # 232,200 ≥ 216,000


def test_the_same_rate_on_a_smaller_contract_fails():
    # 2 % of ₹92,88,000 is ₹1,85,760: under the ₹2,16,000 payout though the rates match.
    field = _refused(SALES, {**PURCHASE, "late_penalty_pct": "2"})
    assert field["field"] == "purchase.late_penalty_pct"
    assert "185,760.00" in field["message"] and "216,000.00" in field["message"]


def test_penalties_compare_in_one_currency():
    # A purchase in AED at 1 AED = 25 INR: the AED recovery is converted before comparing.
    purchase = {**PURCHASE, "currency": "AED", "value_minor": 371_520_00}  # ₹92,88,000 / 25
    check(SALES, purchase, purchase_to_sales_rate=Decimal(25))
    assert _refused(SALES, purchase, Decimal(20))["field"] == "purchase.late_penalty_pct"


@pytest.mark.parametrize(("change", "field"), [
    ({"product": "Ponni Rice"}, "purchase.product"),
    ({"quantity": "450"}, "purchase.quantity"),
    ({"tolerance_pct": "10"}, "purchase.tolerance_pct"),
    ({"incoterm": "CIF"}, "purchase.incoterm"),
    ({"shipment_to": "2027-03-20"}, "purchase.shipment_to"),
    ({"inspection_agency": "Bureau Veritas"}, "purchase.inspection_agency"),
    ({"quality_penalty_pct": "1"}, "purchase.quality_penalty_pct"),
    ({"claim_window_days": 20}, "purchase.claim_window_days"),
    ({"governing_law": "India"}, "purchase.governing_law"),
])
def test_each_rule_names_its_field(change, field):
    assert _refused(SALES, {**PURCHASE, **change})["field"] == field


def test_a_narrower_seller_window_and_tolerance_are_fine():
    check(SALES, {**PURCHASE, "tolerance_pct": "3", "shipment_from": "2027-02-10", "shipment_to": "2027-03-01",
                  "claim_window_days": 45}, purchase_to_sales_rate=Decimal(1))
