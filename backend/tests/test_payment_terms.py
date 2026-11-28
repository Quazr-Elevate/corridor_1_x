"""Payment terms and milestones (M5 · S10, CX-110, A-083)."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from test_admin_accounts import _new_admin
from test_contracts import PURCHASE, REVIEWED, TERMS
from test_lois import SIGN, approve_templates
from test_quotes import parties  # noqa: F401  (fixture)
from test_term_sheets import _issued

from app.core.db import SessionLocal
from app.core.errors import BadRequest
from app.models import Deal, LedgerTransaction, PaymentMilestone
from app.modules.payments.terms import buyer_plan, seller_plan, validate

V = 4_158_000_001  # an odd value, so rounding shows


@pytest.mark.parametrize(("term", "params", "kinds"), [
    ("advance", {}, ["advance"]),
    ("advance_balance_docs", {"advance_pct": 30}, ["advance", "balance"]),
    ("cad", {}, ["cad"]),
    ("lc_sight", {}, ["lc_payment"]),
    ("lc_usance", {"tenor_days": 90}, ["lc_payment"]),
    ("da", {"tenor_days": 60}, ["da_payment"]),
    ("open_account", {"tenor_days": 45}, ["open_account"]),
    ("escrow", {}, ["escrow_funding"]),
])
def test_each_term_makes_milestones_that_add_up_exactly(term, params, kinds):
    plan = buyer_plan(term, V, **params)
    assert [p.kind for p in plan] == kinds
    assert sum(p.amount_minor for p in plan) == V
    seller = seller_plan(term, V, 10, **params)
    assert sum(p.amount_minor for p in seller) == V
    assert seller[-1].kind == "retention" and seller[-1].amount_minor == V // 10
    assert all(p.gate == "pay_seller" for p in seller[:-1]) and seller[-1].due_event == "acceptance"


def test_a_split_advance_and_tenors_land_where_they_should():
    advance, balance = buyer_plan("advance_balance_docs", 10_000_00, advance_pct=30)
    assert (advance.amount_minor, advance.due_event, advance.gate) == (3_000_00, "contract_effective", "start_production")
    assert (balance.amount_minor, balance.due_event, balance.gate) == (7_000_00, "documents", "release_documents")
    (oa,) = buyer_plan("open_account", 10_000_00, tenor_days=45)
    assert (oa.due_event, oa.due_days, oa.gate) == ("shipment", 45, "ship")


@pytest.mark.parametrize(("term", "kw", "message"), [
    ("advance_balance_docs", {}, "advance as a percentage"),
    ("lc_usance", {}, "credit period"),
    ("da", {"tenor_days": 150}, r"beyond the 4-month outlay cap \(120 days\)"),
    ("open_account", {"tenor_days": 30}, "credit limit"),
    ("open_account", {"tenor_days": 30, "credit_limit_minor": V - 1, "credit_insurance_ref": "ECGC-1"}, "credit limit"),
    ("da", {"tenor_days": 30, "credit_limit_minor": V}, "credit insurance"),
    ("barter", {}, "payment terms from the list"),
])
def test_terms_that_cant_be_run_are_refused(term, kw, message):
    with pytest.raises(BadRequest, match=message):
        validate(term, V, outlay_cap_months=4, buyer_side=True, **kw)


def test_credit_rules_apply_to_the_buyer_only():
    # Corridor One X buying from the seller on open account takes no buyer credit risk.
    validate("open_account", V, outlay_cap_months=4, buyer_side=False, tenor_days=30)
    validate("open_account", V, outlay_cap_months=4, buyer_side=True, tenor_days=30,
             credit_limit_minor=V, credit_insurance_ref="ECGC-2026-0042")


async def _signed_lois(p, admin_client, manager, **term_sheet) -> str:
    """Both LOIs signed on a term sheet with the given terms, ready for contracts."""
    code, ts = await _issued(p, admin_client, **term_sheet)
    for c in (p["buyer_client"], p["seller_client"]):
        await c.post(f"/deals/{code}/term-sheets/1/accept", json={"contentSha256": ts["contentSha256"]})
    await approve_templates(admin_client, codes=("loi_buy", "loi_sell", "sales", "purchase"))
    assert (await admin_client.post(f"/admin/deals/{code}/lois")).status_code == 201
    for c in (p["buyer_client"], p["seller_client"]):
        d = (await c.get(f"/deals/{code}/documents")).json()["items"][0]
        await c.post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
        await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})
    return code


async def _sign_contracts(p, manager, code) -> None:
    for c in (p["buyer_client"], p["seller_client"]):
        d = [x for x in (await c.get(f"/deals/{code}/documents")).json()["items"] if x["kind"] == "contract"][0]
        await c.post(f"/deals/{code}/documents/{d['id']}/sign", json={**SIGN, "contentSha256": d["contentSha256"]})
        r = await manager.post(f"/admin/documents/{d['id']}/countersign", json={**SIGN, "contentSha256": d["contentSha256"]})
        assert r.status_code == 200, r.text


async def test_effective_contracts_open_the_milestones_and_the_books(parties, admin_client, make_client):
    p = parties
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    code = await _signed_lois(p, admin_client, manager)  # both sides: LC at sight (the quote fixture)
    r = await admin_client.post(f"/admin/deals/{code}/contracts",
                                json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})
    assert r.status_code == 201, r.text
    await _sign_contracts(p, manager, code)

    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        rows = list(await db.scalars(select(PaymentMilestone).where(PaymentMilestone.deal_id == deal.id)))
        kinds = set(await db.scalars(select(LedgerTransaction.kind).where(LedgerTransaction.deal_id == deal.id)))
    assert deal.status == "CONTRACTED"
    buyer = [m for m in rows if m.leg == "buyer"]
    seller = sorted((m for m in rows if m.leg == "seller"), key=lambda m: m.sequence)
    assert [m.kind for m in buyer] == ["lc_payment"] and buyer[0].amount_minor == 41_580_000_00  # ₹83,160 × 500 MT
    assert [m.kind for m in seller] == ["lc_payment", "retention"]
    assert (seller[0].amount_minor, seller[1].amount_minor) == (32_400_000_00, 3_600_000_00)  # 90 % / 10 %
    assert kinds == {"sales_contract", "purchase_contract"}

    # Each trader sees its own leg; finance sees both and a balanced book.
    mine = (await p["buyer_client"].get(f"/deals/{code}/milestones")).json()["items"]
    theirs = (await p["seller_client"].get(f"/deals/{code}/milestones")).json()["items"]
    assert [m["kind"] for m in mine] == ["lc_payment"]
    assert [m["kind"] for m in theirs] == ["lc_payment", "retention"] and "41580000" not in str(theirs)
    _, finance = await _new_admin(admin_client, make_client, role="finance", email="fin@cor1x.test")
    assert len((await finance.get(f"/admin/deals/{code}/milestones")).json()["items"]) == 3
    assert (await finance.get(f"/admin/deals/{code}/ledger")).json()["balanced"] is True
    assert (await manager.get(f"/admin/deals/{code}/milestones")).status_code == 403  # the desk isn't finance


async def test_credit_terms_need_a_limit_insurance_and_a_tenor_inside_the_cap(parties, admin_client, make_client):
    p = parties
    _, manager = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    code = await _signed_lois(p, admin_client, manager, buyerPaymentTerms="open_account")
    url = f"/admin/deals/{code}/contracts"
    body = {"purchase": PURCHASE, "legalReviewNote": REVIEWED}
    r = await admin_client.post(url, json={**body, "sales": {**TERMS, "tenorDays": 45}})
    assert r.status_code == 400 and "credit limit" in r.json()["detail"]
    credit = {"tenorDays": 45, "creditLimitMinor": 50_000_000_00, "creditInsuranceRef": "ECGC-2026-0042"}
    r = await admin_client.post(url, json={**body, "sales": {**TERMS, **credit, "tenorDays": 150}})
    assert r.status_code == 400 and "outlay cap" in r.json()["detail"]
    r = await admin_client.post(url, json={**body, "sales": {**TERMS, **credit}})
    assert r.status_code == 201, r.text
    await _sign_contracts(p, manager, code)
    (oa,) = (await p["buyer_client"].get(f"/deals/{code}/milestones")).json()["items"]
    assert (oa["kind"], oa["dueEvent"], oa["dueDays"]) == ("open_account", "shipment", 45)
