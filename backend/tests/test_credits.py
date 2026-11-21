"""Credits (CX-084, CX-085): the wallet and its ledger, the free-RFQ quota,
checkout, the payment webhook, plan expiry and the admin price settings."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta

import httpx
import pytest
from conftest import fill_mandatory, set_status, signup_and_login
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from test_admin_accounts import _new_admin

from app.core.db import SessionLocal
from app.core.errors import PaymentRequired
from app.core.time import utcnow
from app.integrations import payments
from app.models import (
    AdminAction,
    BusinessStatus,
    CreditFreeQuota,
    CreditLedgerEntry,
    CreditWallet,
    PaymentEvent,
    PlanPurchase,
    User,
)
from app.modules.credits import service as credits

SECRET = "whsec_test_0123456789abcdef"


@pytest.fixture
def checkout():
    """The no-network payment provider, as development runs it."""
    payments.configure(payments.PaymentsConfig(provider="test", key_id="rzp_test_key", webhook_secret=SECRET))
    yield
    payments.configure(payments.PaymentsConfig())


def _event(order_id: str, *, amount: int, kind: str = "payment.captured", currency: str = "INR", payment="pay_1"):
    status = "captured" if kind == "payment.captured" else "failed"
    entity = {"id": payment, "order_id": order_id, "amount": amount, "currency": currency, "status": status}
    return json.dumps({"event": kind, "payload": {"payment": {"entity": entity}}}).encode()


async def _deliver(c, body: bytes, *, event_id: str = "evt_1", signature: str | None = None, provider="test"):
    headers = {
        "content-type": "application/json",
        "x-razorpay-signature": signature if signature is not None else payments.sign(body, SECRET),
        "x-razorpay-event-id": event_id,
    }
    return await c.post(f"/webhooks/payments/{provider}", content=body, headers=headers)


async def _buy(c, plan="topup-25", key="key-00000001", *, verify=True):
    """Open a checkout. Only a verified company can buy (A-050), so the
    caller's company is verified first unless ``verify`` is False."""
    if verify:
        me = (await c.get("/me")).json()
        if me.get("status") != "verified":
            await set_status(me["userId"], BusinessStatus.verified)
    return await c.post("/wallet/purchases", json={"planCode": plan}, headers={"Idempotency-Key": key})


async def _top_up(c, anon, *, plan="topup-25", key="key-00000001", event_id="evt_1") -> dict:
    """Checkout and the processor's confirmation: 25 credits in the wallet."""
    order = (await _buy(c, plan, key)).json()
    r = await _deliver(anon, _event(order["providerOrderId"], amount=order["amountMinor"]), event_id=event_id)
    assert r.status_code == 200 and r.json() == {"received": True}
    return order


async def _user(user_id: str) -> tuple:
    db = SessionLocal()
    return db, await db.get(User, uuid.UUID(user_id))


async def _spend(user_id: str, action: str, key: str):
    db, user = await _user(user_id)
    try:
        line = await credits.spend(db, user, action, idempotency_key=key, reference=("rfq", key))
        await db.commit()
        return line.amount, line.balance_after, line.free
    finally:
        await db.close()


# ── Wallet ───────────────────────────────────────────────────────────


async def test_a_new_wallet_is_empty_and_says_what_things_cost(client, make_client):
    assert (await make_client().get("/wallet")).status_code == 401
    await signup_and_login(client, "owner@kaverifoods.in")
    w = (await client.get("/wallet")).json()
    assert w["balance"] == 0 and w["plan"] is None and w["freeRfqs"] is None
    assert w["checkoutAvailable"] is False
    prices = {p["action"]: p for p in w["prices"]}
    assert set(prices) == {"RFQ_POST", "OFFER_UNLOCK", "RFQ_VIEW", "LISTING_BOOST", "AI_QUERY", "SAMPLE_FEE"}
    assert all(p["isPlaceholder"] for p in prices.values())  # the client has not set them (A-031)
    assert (await client.get("/wallet/ledger")).json() == {"total": 0, "items": []}
    plans = (await client.get("/wallet/plans")).json()["items"]
    assert [p["code"] for p in plans] == ["starter", "growth", "topup-25"]


async def test_spend_debits_once_and_refuses_what_the_balance_cannot_cover(client, make_client, checkout):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    with pytest.raises(PaymentRequired) as short:
        await _spend(me["userId"], "OFFER_UNLOCK", "unlock-1")
    assert short.value.detail == "This costs 2 credits and you have 0. Top up your wallet to continue."
    assert short.value.status_code == 402 and short.value.code == "credits.insufficient"

    await _top_up(client, make_client())
    assert await _spend(me["userId"], "OFFER_UNLOCK", "unlock-1") == (-2, 23, False)
    # A retry with the same key is the same line: nothing more is charged.
    assert await _spend(me["userId"], "OFFER_UNLOCK", "unlock-1") == (-2, 23, False)
    assert await _spend(me["userId"], "LISTING_BOOST", "boost-1") == (-10, 13, False)

    ledger = (await client.get("/wallet/ledger")).json()
    assert ledger["total"] == 3
    assert [(l["entryType"], l["amount"], l["balanceAfter"]) for l in ledger["items"]] == [
        ("LISTING_BOOST", -10, 13), ("OFFER_UNLOCK", -2, 23), ("TOP_UP", 25, 25),
    ]
    assert (await client.get("/wallet")).json()["balance"] == 13
    async with SessionLocal() as db:
        assert await credits.reconciles(db, uuid.UUID(me["businessId"]))


async def test_two_spends_cannot_use_the_same_credits(client, make_client, checkout):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    await _top_up(client, make_client())  # 25 credits; a boost costs 10
    results = await asyncio.gather(
        *(_spend(me["userId"], "LISTING_BOOST", f"boost-{i}") for i in range(4)), return_exceptions=True
    )
    paid = [r for r in results if not isinstance(r, Exception)]
    refused = [r for r in results if isinstance(r, PaymentRequired)]
    assert len(paid) == 2 and len(refused) == 2
    assert (await client.get("/wallet")).json()["balance"] == 5
    async with SessionLocal() as db:
        assert await credits.reconciles(db, uuid.UUID(me["businessId"]))


async def test_the_database_refuses_a_negative_balance_and_a_wrong_sign(client):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    await client.get("/wallet")
    bid = uuid.UUID(me["businessId"])

    async def rejects(statement, name):
        async with SessionLocal() as db:
            with pytest.raises(IntegrityError) as err:
                await db.execute(statement)
            assert name in str(err.value.orig)

    await rejects(update(CreditWallet).where(CreditWallet.business_id == bid).values(balance=-1), "ck_credit_wallets_balance")
    line = dict(id=uuid.uuid4(), business_id=bid, balance_after=0, free=False)
    await rejects(insert(CreditLedgerEntry).values(**line, entry_type="RFQ_POST", amount=5), "ck_credit_ledger_sign")
    await rejects(insert(CreditLedgerEntry).values(**line, entry_type="TOP_UP", amount=0), "ck_credit_ledger_sign")
    await rejects(insert(CreditLedgerEntry).values(**line, entry_type="GIFT", amount=5), "ck_credit_ledger_entry_type")


async def test_a_company_sees_only_its_own_ledger(client, make_client, checkout):
    await signup_and_login(client, "owner@kaverifoods.in")
    await _top_up(client, make_client())
    other = make_client()
    await signup_and_login(other, "second@othermill.in")
    assert (await other.get("/wallet")).json()["balance"] == 0
    assert (await other.get("/wallet/ledger")).json()["total"] == 0


# ── Free quota ───────────────────────────────────────────────────────


async def test_free_rfqs_belong_to_the_registration_number_not_the_account(client, make_client, checkout):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    await fill_mandatory(client, n=7)  # GSTIN 07AAAAA0007A1Z5
    assert (await client.get("/wallet")).json()["freeRfqs"] is None  # not verified yet
    await set_status(me["userId"], BusinessStatus.verified)
    assert (await client.get("/wallet")).json()["freeRfqs"] == {"allowance": 10, "used": 0, "remaining": 10}

    for i in range(10):
        assert await _spend(me["userId"], "RFQ_POST", f"rfq-{i}") == (0, 0, True)
    assert await _spend(me["userId"], "RFQ_POST", "rfq-3") == (0, 0, True)  # a retry uses nothing
    assert (await client.get("/wallet")).json()["freeRfqs"]["remaining"] == 0
    with pytest.raises(PaymentRequired):
        await _spend(me["userId"], "RFQ_POST", "rfq-10")  # the eleventh costs credits
    await _top_up(client, make_client())
    assert await _spend(me["userId"], "RFQ_POST", "rfq-10") == (-5, 20, False)

    # Delete the account and come back with the same GSTIN: no fresh ten.
    assert (await client.delete("/me")).status_code == 204
    again = make_client()
    me2 = await signup_and_login(again, "owner2@kaverifoods.in")
    await fill_mandatory(again, n=7)
    await set_status(me2["userId"], BusinessStatus.verified)
    assert (await again.get("/wallet")).json()["freeRfqs"] == {"allowance": 10, "used": 10, "remaining": 0}
    with pytest.raises(PaymentRequired):
        await _spend(me2["userId"], "RFQ_POST", "rfq-new")
    async with SessionLocal() as db:
        (quota,) = list(await db.scalars(select(CreditFreeQuota)))
        assert str(quota.business_id) == me2["businessId"] and quota.used == 10


# ── Checkout ─────────────────────────────────────────────────────────


async def test_checkout_needs_a_key_a_real_plan_and_a_processor(client, make_client):
    await signup_and_login(client, "owner@kaverifoods.in")
    assert (await make_client().post("/wallet/purchases", json={"planCode": "starter"})).status_code == 401
    r = await client.post("/wallet/purchases", json={"planCode": "starter"})
    assert r.status_code == 400 and "Idempotency-Key" in r.json()["detail"]
    # No processor configured: nothing is created.
    r = await _buy(client, "starter")
    assert r.status_code == 503 and r.json()["code"] == "service.unavailable"
    async with SessionLocal() as db:
        assert list(await db.scalars(select(PlanPurchase))) == []


async def test_checkout_is_idempotent_on_the_key(client, checkout):
    await signup_and_login(client, "owner@kaverifoods.in")
    assert (await _buy(client, "nope", "key-00000009")).status_code == 404
    first = await _buy(client, "starter", "key-00000001")
    assert first.status_code == 201, first.text
    order = first.json()
    assert order["status"] == "created" and order["amountMinor"] == 99900 and order["currency"] == "INR"
    assert order["providerOrderId"].startswith("order_test_") and order["checkoutKey"] == "rzp_test_key"
    assert (await _buy(client, "starter", "key-00000001")).json() == order  # the retry gets the same order
    r = await _buy(client, "growth", "key-00000001")
    assert r.status_code == 409 and "different purchase" in r.json()["detail"]
    assert (await _buy(client, "starter", "key-00000002")).json()["id"] != order["id"]
    async with SessionLocal() as db:
        assert len(list(await db.scalars(select(PlanPurchase)))) == 2
    assert (await client.get("/wallet")).json()["balance"] == 0  # opening a checkout credits nothing


async def test_webhook_credits_once_and_only_when_signed_and_matching(client, make_client, checkout):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    order = (await _buy(client, "starter")).json()
    anon = make_client()
    paid = _event(order["providerOrderId"], amount=99900)

    assert (await _deliver(anon, paid, signature="")).status_code == 401
    assert (await _deliver(anon, paid, signature=payments.sign(paid, "wrong-secret"))).status_code == 401
    assert (await _deliver(anon, paid, provider="razorpay")).status_code == 404
    assert (await _deliver(anon, b"not json", event_id="evt_x")).status_code == 400
    # Signed, but for less than the plan costs: acknowledged and not credited.
    short = _event(order["providerOrderId"], amount=100)
    assert (await _deliver(anon, short, event_id="evt_short")).status_code == 200
    assert (await client.get("/wallet")).json()["balance"] == 0

    assert (await _deliver(anon, paid, event_id="evt_paid")).status_code == 200
    w = (await client.get("/wallet")).json()
    assert w["balance"] == 50 and w["plan"]["code"] == "starter" and w["plan"]["state"] == "active"
    assert w["plan"]["name"] == "Starter"
    # The processor retries, and sends a second event for the same payment.
    assert (await _deliver(anon, paid, event_id="evt_paid")).status_code == 200
    assert (await _deliver(anon, paid, event_id="evt_paid_again")).status_code == 200
    assert (await client.get("/wallet")).json()["balance"] == 50

    async with SessionLocal() as db:
        purchase = await db.get(PlanPurchase, uuid.UUID(order["id"]))
        assert (purchase.status, purchase.invoice_number, purchase.provider_payment_id) == ("paid", 1, "pay_1")
        events = {e.event_id: e.outcome for e in await db.scalars(select(PaymentEvent))}
        assert events == {"evt_short": "mismatch", "evt_paid": "credited", "evt_paid_again": "ignored"}
        lines = list(await db.scalars(select(CreditLedgerEntry)))
        assert [(l.entry_type, l.amount, l.reference_type, l.reference_id) for l in lines] == [
            ("PLAN_PURCHASE", 50, "purchase", order["id"])
        ]
        assert await credits.reconciles(db, uuid.UUID(me["businessId"]))


async def test_a_failed_payment_credits_nothing(client, make_client, checkout):
    await signup_and_login(client, "owner@kaverifoods.in")
    order = (await _buy(client)).json()
    failed = _event(order["providerOrderId"], amount=order["amountMinor"], kind="payment.failed")
    assert (await _deliver(make_client(), failed)).status_code == 200
    assert (await client.get("/wallet")).json()["balance"] == 0
    async with SessionLocal() as db:
        assert (await db.get(PlanPurchase, uuid.UUID(order["id"]))).status == "failed"


async def test_a_plan_runs_out_through_grace_to_free_and_renewal_adds_time(client, make_client, checkout):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    anon = make_client()
    await _top_up(client, anon, plan="starter", key="key-00000001", event_id="evt_1")
    first = (await client.get("/wallet")).json()["plan"]
    # Renewing early adds thirty days to the time left.
    await _top_up(client, anon, plan="starter", key="key-00000002", event_id="evt_2")
    second = (await client.get("/wallet")).json()
    assert (second["balance"], second["planCredits"]) == (100, 100)
    from datetime import datetime

    gap = datetime.fromisoformat(second["plan"]["expiresAt"]) - datetime.fromisoformat(first["expiresAt"])
    assert gap == timedelta(days=30)

    async def expire(days_ago: int):
        async with SessionLocal() as db:
            await db.execute(
                update(CreditWallet)
                .where(CreditWallet.business_id == uuid.UUID(me["businessId"]))
                .values(plan_expires_at=utcnow() - timedelta(days=days_ago))
            )
            await db.commit()

    # A top-up and a spend: plan credits go first, top-up credits don't expire.
    await _top_up(client, anon, plan="topup-25", key="key-00000003", event_id="evt_3")
    assert await _spend(me["userId"], "RFQ_POST", "rfq-1") == (-5, 120, False)
    mid = (await client.get("/wallet")).json()
    assert (mid["balance"], mid["planCredits"]) == (120, 95)

    await expire(3)
    ended = (await client.get("/wallet")).json()
    assert ended["plan"]["state"] == "grace"
    # The plan has ended: its credits are written off once, the top-up stays (A-051).
    assert (ended["balance"], ended["planCredits"]) == (25, 0)
    lines = (await client.get("/wallet/ledger")).json()["items"]
    assert (lines[0]["entryType"], lines[0]["amount"]) == ("EXPIRY", -95)
    await expire(8)  # past the seven days of grace
    lapsed = (await client.get("/wallet")).json()
    assert lapsed["plan"] is None and lapsed["balance"] == ended["balance"]
    assert [l["entryType"] for l in (await client.get("/wallet/ledger")).json()["items"]].count("EXPIRY") == 1


# ── Admin ────────────────────────────────────────────────────────────


async def test_prices_and_plans_are_set_by_a_super_admin_and_audited(client, admin_client, make_client):
    _, reviewer = await _new_admin(admin_client, make_client)
    assert (await reviewer.get("/admin/credits/prices")).status_code == 403
    assert (await reviewer.put("/admin/credits/prices/RFQ_POST", json={"credits": 1})).status_code == 403
    await signup_and_login(client, "owner@kaverifoods.in")
    assert (await client.put("/admin/credits/prices/RFQ_POST", json={"credits": 1})).status_code == 401

    assert (await admin_client.put("/admin/credits/prices/RFQ_POST", json={"credits": -1})).status_code == 422
    assert (await admin_client.put("/admin/credits/prices/FREE_LUNCH", json={"credits": 1})).status_code == 422
    r = await admin_client.put("/admin/credits/prices/RFQ_POST", json={"credits": 8})
    assert r.status_code == 200 and r.json() == {"action": "RFQ_POST", "credits": 8, "isPlaceholder": False}
    prices = {p["action"]: p for p in (await client.get("/wallet")).json()["prices"]}
    assert prices["RFQ_POST"] == {"action": "RFQ_POST", "credits": 8, "isPlaceholder": False}
    assert prices["AI_QUERY"]["isPlaceholder"] is True

    assert (await admin_client.put("/admin/credits/plans/topup-25", json={"periodDays": 30})).status_code == 400
    assert (await admin_client.put("/admin/credits/plans/nope", json={"active": False})).status_code == 404
    r = await admin_client.put("/admin/credits/plans/growth", json={"priceMinor": 299900, "active": False})
    assert r.status_code == 200 and r.json()["priceMinor"] == 299900 and r.json()["isPlaceholder"] is False
    assert [p["code"] for p in (await client.get("/wallet/plans")).json()["items"]] == ["starter", "topup-25"]
    assert len((await admin_client.get("/admin/credits/plans")).json()["items"]) == 3

    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AdminAction).where(AdminAction.action.like("credit_%")).order_by(AdminAction.created_at)))
    assert [(r.action, r.target_id, r.details) for r in rows] == [
        ("credit_price.update", "RFQ_POST", {"from": 5, "to": 8}),
        ("credit_plan.update", "growth", {"fields": ["active", "price_minor"]}),
    ]


# ── The Razorpay provider (no network: a mock transport) ─────────────


def _razorpay(handler) -> payments.RazorpayProvider:
    config = payments.PaymentsConfig(provider="razorpay", key_id="rzp_live_k", key_secret="s3cret", webhook_secret=SECRET)
    return payments.RazorpayProvider(config, transport=httpx.MockTransport(handler))


async def test_razorpay_order_is_created_with_basic_auth_and_checked():
    seen = {}

    def ok(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"id": "order_ABC123", "amount": 99900, "currency": "INR", "status": "created"})

    order = await _razorpay(ok).create_order(amount_minor=99900, currency="INR", receipt="r-1")
    assert order == payments.Order(id="order_ABC123", amount_minor=99900, currency="INR")
    assert seen["url"] == "https://api.razorpay.com/v1/orders" and seen["auth"].startswith("Basic ")
    assert seen["body"] == {"amount": 99900, "currency": "INR", "receipt": "r-1"}

    # An answer for a different amount, a refusal and an outage are all errors.
    wrong = lambda r: httpx.Response(200, json={"id": "order_X", "amount": 1, "currency": "INR"})  # noqa: E731
    refused = lambda r: httpx.Response(401, json={"error": {"description": "bad key"}})  # noqa: E731

    def down(request):
        raise httpx.ConnectError("no route")

    for handler in (wrong, refused, down):
        with pytest.raises(payments.PaymentsError):
            await _razorpay(handler).create_order(amount_minor=99900, currency="INR", receipt="r-1")


def test_webhook_signature_is_hmac_sha256_of_the_raw_body():
    body = _event("order_ABC123", amount=99900)
    provider = _razorpay(lambda r: httpx.Response(500))
    headers = {"x-razorpay-signature": payments.sign(body, SECRET), "x-razorpay-event-id": "evt_9"}
    event = provider.read_webhook(body, headers)
    assert (event.paid, event.order_id, event.amount_minor, event.currency) == (True, "order_ABC123", 99900, "INR")
    with pytest.raises(payments.InvalidSignature):
        provider.read_webhook(body + b" ", headers)  # one byte changed
    with pytest.raises(payments.InvalidEvent):
        provider.read_webhook(body, {"x-razorpay-signature": payments.sign(body, SECRET)})  # no event id
    assert payments.sign(b"abc", "key") == "9c196e32dc0175f86f4b1cb89289d6619de6bee699e4c378e68309ed97a1a6ab"


def test_the_test_provider_is_refused_outside_debug():
    from app.core.config import Settings

    base = dict(
        debug=False, test_harness=False, cookie_secure=None, session_secret="x" * 40, email_provider="resend",
        database_url="postgresql://u:p@db/cor1x",
    )
    assert any("PAYMENT_PROVIDER=test" in p for p in Settings(**base, payment_provider="test").insecure_defaults())
    assert any("PAYMENT_PROVIDER=test" in p for p in Settings(**base, payment_provider=" Test").insecure_defaults())
    assert any("RAZORPAY" in p for p in Settings(**base, payment_provider="razorpay").insecure_defaults())
    assert not Settings(**base, payment_provider="none").insecure_defaults()


async def test_only_a_verified_company_can_buy(client, checkout):
    await signup_and_login(client, "owner@kaverifoods.in")
    assert (await client.get("/wallet")).json()["checkoutAvailable"] is False
    r = await _buy(client, verify=False)
    assert r.status_code == 403 and r.json()["detail"] == "Get your business verified before buying credits."


def test_the_financial_year_turns_on_1_april_in_india():
    from datetime import datetime, timezone

    assert credits.financial_year(datetime(2026, 3, 31, 18, 29, tzinfo=timezone.utc)) == "2025-26"  # 23:59 IST
    assert credits.financial_year(datetime(2026, 3, 31, 18, 31, tzinfo=timezone.utc)) == "2026-27"  # 00:01 IST
    assert credits.financial_year(datetime(2099, 12, 1, tzinfo=timezone.utc)) == "2099-00"


async def test_invoice_numbers_count_from_one_in_each_financial_year(client, make_client, checkout):
    from app.models import InvoiceCounter

    anon = make_client()
    await signup_and_login(client, "owner@kaverifoods.in")
    await _top_up(client, anon, key="key-00000001", event_id="evt_1")
    await _top_up(client, anon, key="key-00000002", event_id="evt_2")
    fy = credits.financial_year(utcnow())
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(PlanPurchase).order_by(PlanPurchase.invoice_number)))
        assert [(p.invoice_fy, p.invoice_number) for p in rows] == [(fy, 1), (fy, 2)]
        from app.modules.credits.schemas import purchase_to_read

        assert purchase_to_read(rows[1], "rzp_test_key").invoice_ref == f"C1X/{fy}/0002"
        # A new year starts again at 1.
        db.add(InvoiceCounter(fy="2099-00", last_number=0))
        await db.commit()
        assert await credits._next_invoice_number(db, "2099-00") == 1
        assert await credits._next_invoice_number(db, "2100-01") == 1
