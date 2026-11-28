"""Bank accounts and statement matching (M5 · S10, CX-020, CX-112, A-083).

A buyer's payment clears its milestone only on an exact match from one of
its verified accounts; anything else waits for a person, who must meet the
same rules. Account numbers are stored encrypted and shown masked."""
from __future__ import annotations

import uuid

from conftest import signup_and_login
from sqlalchemy import select
from test_admin_accounts import _new_admin
from test_contracts import PURCHASE, REVIEWED, TERMS
from test_payment_terms import _sign_contracts, _signed_lois
from test_quotes import parties  # noqa: F401  (fixture)

from app.core.db import SessionLocal
from app.models import AdminAction, BankAccount, Deal, PaymentMilestone

BUYER_ACCOUNT = {"currency": "INR", "country": "IN", "bankName": "HDFC Bank", "routingCode": "HDFC0001234",
                 "accountNumber": "5010 0123 4567 89", "holderName": "Buyer Foods Pvt Ltd"}
MAP = {"name": "HDFC current account", "dateFormat": "%d/%m/%Y", "defaultCurrency": "INR",
       "columns": {"date": "Txn Date", "amount": "Credit", "reference": "Narration", "payer_account": "Remitter A/c"}}
LC = "41580000.00"  # the buyer's one milestone: an LC at sight for ₹4,15,80,000.00


def _csv(*rows: tuple[str, str, str, str]) -> bytes:
    lines = ["Txn Date,Credit,Narration,Remitter A/c"] + [",".join(f'"{c}"' for c in r) for r in rows]
    return ("\n".join(lines) + "\n").encode()


async def _contracted(p, admin_client, make_client) -> str:
    _, desk = await _new_admin(admin_client, make_client, role="desk_manager", email="mgr@cor1x.test")
    code = await _signed_lois(p, admin_client, desk)
    r = await admin_client.post(f"/admin/deals/{code}/contracts",
                                json={"sales": TERMS, "purchase": PURCHASE, "legalReviewNote": REVIEWED})
    assert r.status_code == 201, r.text
    await _sign_contracts(p, desk, code)
    return code


async def _finance(admin_client, make_client):
    _, fin = await _new_admin(admin_client, make_client, role="finance", email="fin@cor1x.test")
    _, mgr = await _new_admin(admin_client, make_client, role="finance_manager", email="finmgr@cor1x.test")
    return fin, mgr


async def _verified_buyer_account(p, mgr) -> str:
    r = await p["buyer_client"].post("/me/bank-accounts", json=BUYER_ACCOUNT)
    assert r.status_code == 201, r.text
    acc = r.json()
    r = await mgr.post(f"/admin/bank-accounts/{acc['id']}/verify", json={"note": "Penny drop ref PD-77821 matched."})
    assert r.status_code == 200, r.text
    return acc["id"]


# ── Bank accounts ────────────────────────────────────────────────────


async def test_an_account_is_stored_encrypted_shown_masked_and_verified_by_a_manager(parties, admin_client, make_client):
    p = parties
    fin, mgr = await _finance(admin_client, make_client)
    r = await p["buyer_client"].post("/me/bank-accounts", json={**BUYER_ACCOUNT, "routingCode": "HDFC1234"})
    assert r.status_code == 400 and "IFSC" in r.json()["detail"]
    r = await p["buyer_client"].post("/me/bank-accounts", json=BUYER_ACCOUNT)
    assert r.status_code == 201
    acc = r.json()
    assert acc["accountMasked"] == "••••6789" and acc["status"] == "pending"
    assert "50100123456789" not in r.text and "Buyer Foods" not in r.text
    async with SessionLocal() as db:
        row = await db.get(BankAccount, uuid.UUID(acc["id"]))
    assert "50100123456789" not in row.account_encrypted and row.account_last4 == "6789"

    # The seller can't see it; finance sees it by company code, masked.
    assert (await p["seller_client"].get("/me/bank-accounts")).json()["items"] == []
    pending = (await fin.get("/admin/bank-accounts/pending")).json()["items"]
    assert pending[0]["accountMasked"] == "••••6789" and pending[0]["companyCode"]
    # Finance reads; only a finance manager verifies or reveals.
    note = {"note": "Penny drop ref PD-77821 matched."}
    assert (await fin.post(f"/admin/bank-accounts/{acc['id']}/verify", json=note)).status_code == 403
    r = await mgr.post(f"/admin/bank-accounts/{acc['id']}/verify", json=note)
    assert r.status_code == 200 and r.json()["coolingOffUntil"]
    assert (await fin.post(f"/admin/bank-accounts/{acc['id']}/reveal", json={"reason": "Checking a payment"})).status_code == 403
    r = await mgr.post(f"/admin/bank-accounts/{acc['id']}/reveal", json={"reason": "Checking a payment against the bank."})
    assert r.json() == {"id": acc["id"], "accountNumber": "50100123456789", "holderName": "Buyer Foods Pvt Ltd"}
    async with SessionLocal() as db:
        actions = set(await db.scalars(select(AdminAction.action).where(AdminAction.action.like("bank_account.%"))))
    assert actions == {"bank_account.verified", "bank_account.revealed"}

    # A new account for the currency retires the old one and starts again.
    r = await p["buyer_client"].post("/me/bank-accounts", json={**BUYER_ACCOUNT, "accountNumber": "50100999988887"})
    statuses = [a["status"] for a in (await p["buyer_client"].get("/me/bank-accounts")).json()["items"]]
    assert statuses == ["pending", "retired"]


async def test_an_unverified_business_cant_add_an_account(client):
    await signup_and_login(client, "nobank@kaverifoods.in")
    assert (await client.post("/me/bank-accounts", json=BUYER_ACCOUNT)).status_code == 403


# ── Statements ───────────────────────────────────────────────────────


async def test_an_exact_payment_from_the_buyers_account_clears_its_milestone(parties, admin_client, make_client):
    p = parties
    code = await _contracted(p, admin_client, make_client)
    fin, mgr = await _finance(admin_client, make_client)
    await _verified_buyer_account(p, mgr)
    r = await fin.post("/admin/statement-maps", json={**MAP, "columns": {"date": "Txn Date"}})
    assert r.status_code == 400 and "amount" in r.json()["detail"]
    stmap = (await fin.post("/admin/statement-maps", json=MAP)).json()

    statement = _csv(
        ("02/12/2026", LC, f"NEFT {code} LC payment", "5010-0123-4567-89"),  # matches
        ("02/12/2026", LC, f"NEFT {code} again", "99887766554433"),         # not the buyer's account
        ("03/12/2026", "-500.00", "Bank charges", ""),                       # a debit: skipped
        ("03/12/2026", "1000.00", f"{code} part", "50100123456789"),          # not the milestone's amount
    )
    r = await fin.post("/admin/statements", data={"mapId": stmap["id"]},
                       files={"file": ("hdfc-dec.csv", statement, "text/csv")})
    assert r.status_code == 201, r.text
    assert r.json() | {"statementId": None} == {"statementId": None, "linesTotal": 4, "linesNew": 3,
                                                "linesMatched": 1, "debitsSkipped": 1}
    # The same file again is refused.
    r = await fin.post("/admin/statements", data={"mapId": stmap["id"]}, files={"file": ("again.csv", statement, "text/csv")})
    assert r.status_code == 409

    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        (lc,) = list(await db.scalars(select(PaymentMilestone).where(
            PaymentMilestone.deal_id == deal.id, PaymentMilestone.leg == "buyer")))
    assert lc.status == "cleared" and lc.cleared_at
    assert (await p["buyer_client"].get(f"/deals/{code}/milestones")).json()["items"][0]["status"] == "cleared"
    books = (await fin.get(f"/admin/deals/{code}/ledger")).json()
    assert books["balanced"]
    assert {l["leg"]: l["balances"] for l in books["legs"]}["buyer"]["buyer_receivable"]["INR"] == 0

    queue = (await fin.get("/admin/statement-lines/unmatched")).json()["items"]
    assert len(queue) == 2 and {q["payerAccountLast4"] for q in queue} == {"4433", "6789"}
    wrong_payer = next(q for q in queue if q["payerAccountLast4"] == "4433")
    r = await fin.post(f"/admin/statement-lines/{wrong_payer['id']}/match",
                       json={"milestoneId": str(lc.id), "note": "Buyer says it paid twice."})
    assert r.status_code == 409  # that milestone is already cleared
    r = await fin.post(f"/admin/statement-lines/{wrong_payer['id']}/set-aside",
                       json={"note": "Not a buyer account; returned to the sender."})
    assert r.status_code == 200 and r.json()["status"] == "ignored"
    assert len((await fin.get("/admin/statement-lines/unmatched")).json()["items"]) == 1

    # An overlapping export adds only the line not seen before.
    overlap = _csv(("02/12/2026", LC, f"NEFT {code} LC payment", "5010-0123-4567-89"),
                   ("05/12/2026", "250.00", "Interest", ""))
    r = await fin.post("/admin/statements", data={"mapId": stmap["id"]}, files={"file": ("overlap.csv", overlap, "text/csv")})
    assert (r.json()["linesNew"], r.json()["linesMatched"]) == (1, 0)


async def test_a_hand_match_still_needs_the_amount_and_the_buyers_account(parties, admin_client, make_client):
    p = parties
    code = await _contracted(p, admin_client, make_client)
    fin, mgr = await _finance(admin_client, make_client)
    await _verified_buyer_account(p, mgr)
    stmap = (await fin.post("/admin/statement-maps", json=MAP)).json()
    # No deal code in the narration: nothing to match on automatically.
    statement = _csv(("02/12/2026", LC, "NEFT FROM BUYER FOODS", "50100123456789"),
                     ("02/12/2026", LC, "NEFT FROM SOMEONE", "11112222333344"))
    r = await fin.post("/admin/statements", data={"mapId": stmap["id"]}, files={"file": ("s.csv", statement, "text/csv")})
    assert r.json()["linesMatched"] == 0
    async with SessionLocal() as db:
        deal = await db.scalar(select(Deal).where(Deal.code == code))
        lc = await db.scalar(select(PaymentMilestone).where(PaymentMilestone.deal_id == deal.id, PaymentMilestone.leg == "buyer"))
    queue = {q["payerAccountLast4"]: q for q in (await fin.get("/admin/statement-lines/unmatched")).json()["items"]}
    body = {"milestoneId": str(lc.id), "note": "Buyer confirmed by email; narration lacked the code."}
    assert (await fin.post(f"/admin/statement-lines/{queue['3344']['id']}/match", json=body)).status_code == 409
    r = await fin.post(f"/admin/statement-lines/{queue['6789']['id']}/match", json=body)
    assert r.status_code == 200 and r.json()["status"] == "matched"
    _, desk = await _new_admin(admin_client, make_client, role="trade_desk", email="desk2@cor1x.test")
    assert (await desk.get("/admin/statement-lines/unmatched")).status_code == 403
