"""Turning effective contracts into payment milestones and opening the books
for them (CX-110, CX-111, A-083).

Called once, in the transaction that makes both contracts effective: the
sales contract's terms give the buyer's milestones, the purchase contract's
the seller's (less the retention). The ledger gets one posting per leg:
the buyer's debt to Corridor One X, and Corridor One X's debt to the seller."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import DealDocument
from app.models.deal import Deal
from app.models.payment import PaymentMilestone
from app.modules.ledger import service as ledger
from app.modules.ledger.service import Line
from app.modules.payments import terms
from app.modules.rfq import seed
from app.modules.rfq import service as settings_source

PARAMS = ("advance_pct", "tenor_days")


def _params(t: dict) -> dict:
    return {k: (int(t[k]) if t.get(k) is not None else None) for k in PARAMS}


async def check_contract_terms(db: AsyncSession, sales: dict, purchase: dict) -> None:
    """Both contracts' payment terms can be run (CX-110). Called before they are sent."""
    cap = int(await settings_source.setting(db, seed.OUTLAY_CAP_MONTHS))
    for t, buyer_side in ((sales, True), (purchase, False)):
        terms.validate(
            t["payment_terms"], t["value_minor"], outlay_cap_months=cap, buyer_side=buyer_side,
            credit_limit_minor=t.get("credit_limit_minor"), credit_insurance_ref=t.get("credit_insurance_ref"),
            **_params(t),
        )


async def generate(db: AsyncSession, deal: Deal, contracts: dict[str, DealDocument], admin_id: uuid.UUID) -> list[PaymentMilestone]:
    """Each leg's milestones, and the opening ledger posting for each leg."""
    retention = int(Decimal(await settings_source.setting(db, seed.RETENTION_PCT)))
    sales, purchase = contracts["buyer"], contracts["seller"]
    plans = {
        "buyer": (sales, terms.buyer_plan(sales.terms["payment_terms"], sales.value_minor, **_params(sales.terms))),
        "seller": (purchase, terms.seller_plan(purchase.terms["payment_terms"], purchase.value_minor, retention,
                                               **_params(purchase.terms))),
    }
    rows = []
    for leg, (contract, planned) in plans.items():
        for n, p in enumerate(planned, start=1):
            rows.append(PaymentMilestone(
                id=uuid.uuid4(), deal_id=deal.id, contract_id=contract.id, leg=leg, sequence=n, kind=p.kind,
                amount_minor=p.amount_minor, currency=contract.currency, due_event=p.due_event, due_days=p.due_days,
                gate=p.gate, status="open",
            ))
    db.add_all(rows)
    # The buy leg: the buyer owes the sales value. The sell leg: Corridor One
    # X owes the purchase value. corridor_margin carries both sides, so its
    # balance is the margin (in each currency's own terms).
    await ledger.post(
        db, kind="sales_contract", memo=f"{deal.code}: sales contract in effect", deal_id=deal.id, admin_id=admin_id,
        idempotency_key=f"contract:{sales.id}", reference=("deal_document", str(sales.id)), lines=[
            Line("buyer_receivable", sales.value_minor, sales.currency, "buyer"),
            Line("corridor_margin", -sales.value_minor, sales.currency, "buyer"),
        ],
    )
    await ledger.post(
        db, kind="purchase_contract", memo=f"{deal.code}: purchase contract in effect", deal_id=deal.id,
        admin_id=admin_id, idempotency_key=f"contract:{purchase.id}", reference=("deal_document", str(purchase.id)),
        lines=[
            Line("corridor_margin", purchase.value_minor, purchase.currency, "seller"),
            Line("seller_payable", -purchase.value_minor, purchase.currency, "seller"),
        ],
    )
    return rows


async def of_deal(db: AsyncSession, deal_id: uuid.UUID, leg: str | None = None) -> list[PaymentMilestone]:
    stmt = select(PaymentMilestone).where(PaymentMilestone.deal_id == deal_id)
    if leg:
        stmt = stmt.where(PaymentMilestone.leg == leg)
    return list(await db.scalars(stmt.order_by(PaymentMilestone.leg, PaymentMilestone.sequence)))
