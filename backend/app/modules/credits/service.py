"""Credit rules (build plan 17).

* The wallet balance is the sum of the company's ledger lines. A spend is one
  guarded UPDATE (``balance >= cost``) plus one ledger insert in the same
  transaction, so two requests cannot spend the same credits, and the
  ``balance >= 0`` CHECK is the last line if this code is ever wrong.
* Every spend carries an idempotency key; a retry finds the first line.
* The free-RFQ quota belongs to the registration number, not the account.
* A purchase credits the wallet only from a signature-checked webhook whose
  order, amount and currency match what we created. Never from the browser.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    BadRequest,
    Conflict,
    NotFound,
    PaymentRequired,
    ServiceUnavailable,
    Unauthorized,
    UpstreamError,
)
from app.core.time import ensure_aware, utcnow
from app.integrations import payments
from app.models.business import Business
from app.models.business_document import BusinessDocument
from app.models.credits import (
    SPEND_TYPES,
    CreditFreeQuota,
    CreditLedgerEntry,
    CreditPlan,
    CreditPrice,
    CreditWallet,
    IdempotencyKey,
    PaymentEvent,
    PlanPurchase,
)
from app.models.kyb_document_type import KybDocumentType
from app.models.user import User
from app.modules.credits.schemas import (
    FreeQuotaRead,
    PlanState,
    PlanUpdate,
    PurchaseRead,
    WalletRead,
    price_to_read,
    purchase_to_read,
)
from app.modules.credits.seed import FREE_RFQ_ALLOWANCE

log = logging.getLogger("app.credits")

#: Actions with a free allowance per verified company (plan 17.2).
FREE_ALLOWANCES = {"RFQ_POST": FREE_RFQ_ALLOWANCE}
PURCHASE_ROUTE = "wallet.purchase"


# ── Wallet and ledger ────────────────────────────────────────────────


async def wallet_of(db: AsyncSession, business_id: uuid.UUID) -> CreditWallet:
    """The company's wallet, created empty the first time it is needed."""
    wallet = await db.get(CreditWallet, business_id)
    if wallet is not None:
        return wallet
    try:
        async with db.begin_nested():
            db.add(CreditWallet(business_id=business_id, balance=0))
    except IntegrityError:  # another request created it first
        pass
    return await db.scalar(select(CreditWallet).where(CreditWallet.business_id == business_id))


async def _line_for_key(db: AsyncSession, business_id: uuid.UUID, key: str | None) -> CreditLedgerEntry | None:
    if not key:
        return None
    return await db.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.business_id == business_id, CreditLedgerEntry.idempotency_key == key
        )
    )


async def _post(
    db: AsyncSession,
    business_id: uuid.UUID,
    entry_type: str,
    amount: int,
    *,
    idempotency_key: str,
    free: bool = False,
    reference: tuple[str, str] | None = None,
    user_id: uuid.UUID | None = None,
    note: str | None = None,
) -> CreditLedgerEntry:
    """Move the balance and write the ledger line together, in the caller's
    transaction. Raises :class:`PaymentRequired` when the balance is short."""
    existing = await _line_for_key(db, business_id, idempotency_key)
    if existing is not None:
        return existing
    await wallet_of(db, business_id)
    try:
        async with db.begin_nested():
            moved = await db.execute(
                update(CreditWallet)
                .where(CreditWallet.business_id == business_id, CreditWallet.balance + amount >= 0)
                .values(balance=CreditWallet.balance + amount, updated_at=utcnow())
                .execution_options(synchronize_session=False)
            )
            if moved.rowcount != 1:
                raise PaymentRequired("Not enough credits.")
            balance = await db.scalar(select(CreditWallet.balance).where(CreditWallet.business_id == business_id))
            line = CreditLedgerEntry(
                business_id=business_id, entry_type=entry_type, amount=amount, balance_after=balance, free=free,
                reference_type=reference[0] if reference else None,
                reference_id=reference[1] if reference else None,
                idempotency_key=idempotency_key, created_by_user_id=user_id, note=note, created_at=utcnow(),
            )
            db.add(line)
            await db.flush()
    except IntegrityError:
        # The same key landed from another request; the savepoint undid our move.
        existing = await _line_for_key(db, business_id, idempotency_key)
        if existing is None:
            raise
        return existing
    return line


async def price_of(db: AsyncSession, action: str) -> int:
    price = await db.get(CreditPrice, action)
    if price is None:
        raise BadRequest("That action has no credit price.")
    return price.credits


async def spend(
    db: AsyncSession,
    user: User,
    action: str,
    *,
    idempotency_key: str,
    reference: tuple[str, str] | None = None,
) -> CreditLedgerEntry:
    """Charge the company for one paid action. Uses the free quota first
    where the action has one. Does not commit: the caller commits the spend
    together with the thing it pays for, so neither exists without the other.
    A repeat with the same key returns the first line and charges nothing."""
    if action not in SPEND_TYPES:
        raise BadRequest("Unknown paid action.")
    business = user.business
    existing = await _line_for_key(db, business.id, idempotency_key)
    if existing is not None:
        return existing
    if await _use_free_quota(db, business, action):
        return await _post(
            db, business.id, action, 0, free=True, idempotency_key=idempotency_key, reference=reference,
            user_id=user.id, note="Free quota",
        )
    cost = await price_of(db, action)
    try:
        return await _post(
            db, business.id, action, -cost, idempotency_key=idempotency_key, reference=reference, user_id=user.id
        )
    except PaymentRequired:
        balance = (await wallet_of(db, business.id)).balance
        raise PaymentRequired(
            f"This costs {cost} {_credits(cost)} and you have {balance}. Top up your wallet to continue."
        ) from None


async def refund(db: AsyncSession, business_id: uuid.UUID, spend_key: str, *, note: str) -> CreditLedgerEntry | None:
    """Give back what a spend took, as a REVERSAL line (never by editing the
    first line): the credits, or the free use. Does not commit. Returns None
    when there was no such spend; a second call returns the first reversal."""
    spent = await _line_for_key(db, business_id, spend_key)
    if spent is None:
        return None
    key = f"refund:{spend_key}"
    done = await _line_for_key(db, business_id, key)
    if done is not None:
        return done
    if spent.free:
        await db.execute(
            update(CreditFreeQuota)
            .where(
                CreditFreeQuota.business_id == business_id, CreditFreeQuota.action == spent.entry_type,
                CreditFreeQuota.used > 0,
            )
            .values(used=CreditFreeQuota.used - 1)
            .execution_options(synchronize_session=False)
        )
    return await _post(
        db, business_id, "REVERSAL", -spent.amount, free=spent.free, idempotency_key=key,
        reference=(spent.reference_type, spent.reference_id) if spent.reference_type else None, note=note,
    )


def _credits(n: int) -> str:
    return "credit" if n == 1 else "credits"


async def reconciles(db: AsyncSession, business_id: uuid.UUID) -> bool:
    """Does the stored balance equal the sum of the ledger?"""
    total = await db.scalar(
        select(func.coalesce(func.sum(CreditLedgerEntry.amount), 0)).where(CreditLedgerEntry.business_id == business_id)
    )
    wallet = await db.scalar(select(CreditWallet.balance).where(CreditWallet.business_id == business_id))
    return (wallet or 0) == total


async def list_ledger(db: AsyncSession, user: User, *, limit: int, offset: int) -> tuple[int, list[CreditLedgerEntry]]:
    """The company's ledger lines, newest first."""
    mine = CreditLedgerEntry.business_id == user.business_id
    total = await db.scalar(select(func.count(CreditLedgerEntry.id)).where(mine)) or 0
    rows = await db.scalars(
        select(CreditLedgerEntry)
        .where(mine)
        .order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id)
        .offset(offset)
        .limit(limit)
    )
    return total, list(rows)


# ── Free quota ───────────────────────────────────────────────────────


async def registration_hash(db: AsyncSession, business: Business) -> str | None:
    """The keyed hash of the company's registration number: the value of its
    first required KYB document (GSTIN in India). None until one is on file."""
    return await db.scalar(
        select(BusinessDocument.value_hash)
        .join(KybDocumentType, KybDocumentType.id == BusinessDocument.document_type_id)
        .where(
            BusinessDocument.business_id == business.id,
            BusinessDocument.value_hash.is_not(None),
            KybDocumentType.is_mandatory.is_(True),
        )
        .order_by(KybDocumentType.sort_order, KybDocumentType.name)
        .limit(1)
    )


async def _quota(db: AsyncSession, business: Business, action: str) -> CreditFreeQuota | None:
    """The quota row for this company's registration number, created on first
    use. A number seen before brings its used count with it."""
    if action not in FREE_ALLOWANCES or not business.is_verified:
        return None
    reg = await registration_hash(db, business)
    if reg is None:
        return None
    where = (CreditFreeQuota.action == action, CreditFreeQuota.registration_hash == reg)
    quota = await db.scalar(select(CreditFreeQuota).where(*where))
    if quota is None:
        try:
            async with db.begin_nested():
                db.add(CreditFreeQuota(action=action, registration_hash=reg, business_id=business.id, allowance=FREE_ALLOWANCES[action]))
        except IntegrityError:
            pass
        quota = await db.scalar(select(CreditFreeQuota).where(*where))
    if quota.business_id != business.id:
        quota.business_id = business.id
    return quota


async def _use_free_quota(db: AsyncSession, business: Business, action: str) -> bool:
    quota = await _quota(db, business, action)
    if quota is None:
        return False
    used = await db.execute(
        update(CreditFreeQuota)
        .where(CreditFreeQuota.id == quota.id, CreditFreeQuota.used < CreditFreeQuota.allowance)
        .values(used=CreditFreeQuota.used + 1)
        .execution_options(synchronize_session=False)
    )
    return used.rowcount == 1


# ── Wallet view ──────────────────────────────────────────────────────


def plan_state(wallet: CreditWallet, name: str | None, now: datetime) -> PlanState | None:
    if not wallet.plan_code or wallet.plan_expires_at is None:
        return None
    expires = ensure_aware(wallet.plan_expires_at)
    if now <= expires:
        state = "active"
    elif now <= expires + timedelta(days=settings.plan_grace_days):
        state = "grace"
    else:
        return None  # lapsed: the company is on the Free plan
    return PlanState(code=wallet.plan_code, name=name, expires_at=expires, state=state)


async def wallet_view(db: AsyncSession, user: User) -> WalletRead:
    wallet = await wallet_of(db, user.business_id)
    quota = await _quota(db, user.business, "RFQ_POST")
    await db.commit()  # the wallet or quota row may have just been created
    await db.refresh(wallet)
    plan_name = None
    if wallet.plan_code:
        plan_name = await db.scalar(select(CreditPlan.name).where(CreditPlan.code == wallet.plan_code))
    free = None
    if quota is not None:
        await db.refresh(quota)
        free = FreeQuotaRead(allowance=quota.allowance, used=quota.used, remaining=quota.allowance - quota.used)
    prices = await db.scalars(select(CreditPrice).order_by(CreditPrice.action))
    return WalletRead(
        balance=wallet.balance,
        plan=plan_state(wallet, plan_name, utcnow()),
        free_rfqs=free,
        prices=[price_to_read(p) for p in prices],
        checkout_available=payments.get_provider().name != "none",
    )


async def list_plans(db: AsyncSession, *, active_only: bool = True) -> list[CreditPlan]:
    stmt = select(CreditPlan).order_by(CreditPlan.sort_order, CreditPlan.code)
    if active_only:
        stmt = stmt.where(CreditPlan.active.is_(True))
    return list(await db.scalars(stmt))


# ── Purchases ────────────────────────────────────────────────────────


async def create_purchase(db: AsyncSession, user: User, plan_code: str, idempotency_key: str) -> PurchaseRead:
    """Open a checkout for a plan or a top-up. The same key with the same
    plan returns the first order; with a different plan it is refused."""
    request_hash = hashlib.sha256(plan_code.encode()).hexdigest()
    stored = await _stored_answer(db, user.business_id, idempotency_key)
    if stored is not None:
        if stored.request_hash != request_hash:
            raise Conflict("This Idempotency-Key was already used for a different purchase.")
        return PurchaseRead(**stored.response)

    plan = await db.scalar(select(CreditPlan).where(CreditPlan.code == plan_code, CreditPlan.active.is_(True)))
    if plan is None:
        raise NotFound("That plan is not available.")
    provider = payments.get_provider()
    purchase_id = uuid.uuid4()
    try:
        order = await provider.create_order(
            amount_minor=plan.price_minor, currency=plan.currency, receipt=str(purchase_id)
        )
    except payments.PaymentsNotConfigured:
        raise ServiceUnavailable("Buying credits is not available yet. Try again later.") from None
    except payments.PaymentsError as exc:
        log.warning("payment_order_failed provider=%s error=%s", provider.name, exc)
        raise UpstreamError("The payment service did not answer. Nothing was charged; try again.") from None

    purchase = PlanPurchase(
        id=purchase_id, business_id=user.business_id, plan_id=plan.id, plan_code=plan.code, plan_kind=plan.kind,
        period_days=plan.period_days, credits=plan.credits, amount_minor=plan.price_minor, currency=plan.currency,
        status="created", provider=provider.name, provider_order_id=order.id, created_by_user_id=user.id,
        created_at=utcnow(),
    )
    answer = purchase_to_read(purchase, provider.public_key)
    db.add_all([
        purchase,
        IdempotencyKey(
            business_id=user.business_id, route=PURCHASE_ROUTE, key=idempotency_key, request_hash=request_hash,
            response=answer.model_dump(),
        ),
    ])
    try:
        await db.commit()
    except IntegrityError:  # the same key raced us; answer with what the winner stored
        await db.rollback()
        stored = await _stored_answer(db, user.business_id, idempotency_key)
        if stored is None:
            raise
        return PurchaseRead(**stored.response)
    log.info("purchase_created purchase=%s plan=%s provider=%s", purchase.id, plan.code, provider.name)
    return answer


async def _stored_answer(db: AsyncSession, business_id: uuid.UUID, key: str) -> IdempotencyKey | None:
    return await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.business_id == business_id, IdempotencyKey.route == PURCHASE_ROUTE, IdempotencyKey.key == key
        )
    )


async def handle_webhook(db: AsyncSession, provider_name: str, raw_body: bytes, headers: Mapping[str, str]) -> str:
    """Apply one processor event and return what was done with it:
    ``credited``, ``failed``, ``duplicate``, ``mismatch`` or ``ignored``.
    Anything signed is acknowledged, so the processor stops retrying."""
    provider = payments.get_provider()
    if provider.name != provider_name or provider.name == "none":
        raise NotFound("Not found")
    try:
        event = provider.read_webhook(raw_body, headers)
    except payments.InvalidSignature:
        raise Unauthorized("Invalid signature.") from None
    except payments.InvalidEvent as exc:
        raise BadRequest(str(exc)) from None

    seen = await db.scalar(
        select(PaymentEvent.id).where(PaymentEvent.provider == provider.name, PaymentEvent.event_id == event.event_id)
    )
    if seen is not None:
        return "duplicate"

    purchase = None
    if event.order_id and (event.paid or event.failed):
        purchase = await db.scalar(
            select(PlanPurchase)
            .where(PlanPurchase.provider == provider.name, PlanPurchase.provider_order_id == event.order_id)
            .with_for_update()
        )
    outcome = "ignored"
    if purchase is not None and event.failed and purchase.status == "created":
        purchase.status = "failed"
        purchase.provider_payment_id = event.payment_id
        outcome = "failed"
    elif purchase is not None and event.paid and purchase.status != "paid":
        if (event.amount_minor, (event.currency or "").upper()) != (purchase.amount_minor, purchase.currency):
            log.error(
                "payment_mismatch purchase=%s expected_minor=%s got_minor=%s", purchase.id, purchase.amount_minor,
                event.amount_minor,
            )
            outcome = "mismatch"
        else:
            await _settle(db, purchase, event.payment_id)
            outcome = "credited"
    db.add(
        PaymentEvent(
            provider=provider.name, event_id=event.event_id, event_type=event.event_type,
            purchase_id=purchase.id if purchase else None, outcome=outcome, received_at=utcnow(),
        )
    )
    try:
        await db.commit()
    except IntegrityError:  # the same event was delivered twice at once
        await db.rollback()
        return "duplicate"
    log.info("payment_event provider=%s type=%s outcome=%s", provider.name, event.event_type, outcome)
    return outcome


async def _settle(db: AsyncSession, purchase: PlanPurchase, payment_id: str | None) -> None:
    """Mark the purchase paid, number it, credit the wallet and start or
    extend the plan — one transaction with the event row."""
    now = utcnow()
    purchase.status = "paid"
    purchase.paid_at = now
    purchase.provider_payment_id = payment_id
    purchase.invoice_number = (await db.scalar(select(func.coalesce(func.max(PlanPurchase.invoice_number), 0)))) + 1
    await _post(
        db, purchase.business_id, "PLAN_PURCHASE" if purchase.plan_kind == "plan" else "TOP_UP", purchase.credits,
        idempotency_key=f"purchase:{purchase.id}", reference=("purchase", str(purchase.id)),
        user_id=purchase.created_by_user_id, note=purchase.plan_code,
    )
    if purchase.plan_kind == "plan":
        wallet = await wallet_of(db, purchase.business_id)
        await db.refresh(wallet)
        current = ensure_aware(wallet.plan_expires_at) if wallet.plan_expires_at else None
        # Renewing the same plan early adds to the time left; anything else starts now.
        start = current if current and current > now and wallet.plan_code == purchase.plan_code else now
        wallet.plan_code = purchase.plan_code
        wallet.plan_expires_at = start + timedelta(days=purchase.period_days or 0)


# ── Admin configuration ──────────────────────────────────────────────


async def list_prices(db: AsyncSession) -> list[CreditPrice]:
    return list(await db.scalars(select(CreditPrice).order_by(CreditPrice.action)))


async def set_price(db: AsyncSession, action: str, credits: int) -> tuple[CreditPrice, int]:
    """Set what an action costs. Returns the row and the old value for the audit."""
    price = await db.get(CreditPrice, action)
    if price is None:
        raise NotFound("No such paid action.")
    old = price.credits
    price.credits = credits
    price.is_placeholder = False
    return price, old


async def update_plan(db: AsyncSession, code: str, payload: PlanUpdate) -> tuple[CreditPlan, list[str]]:
    """Change a plan. Purchases already made keep the terms they were bought on."""
    plan = await db.scalar(select(CreditPlan).where(CreditPlan.code == code))
    if plan is None:
        raise NotFound("No such plan.")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "period_days" in changes and plan.kind != "plan":
        raise BadRequest("A top-up has no validity period.")
    for field, value in changes.items():
        setattr(plan, field, value)
    if changes.keys() & {"credits", "price_minor"}:
        plan.is_placeholder = False
    return plan, sorted(changes)
