"""/wallet/* — the caller's own credit wallet — and the payment webhook."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from app.core.errors import BadRequest
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.credits import service
from app.modules.credits.schemas import (
    LedgerPage,
    PlanRead,
    PurchaseCreate,
    PurchaseRead,
    WalletRead,
    WebhookAck,
    line_to_read,
    plan_to_read,
)
from app.ratelimit import RateLimitRule, get_limiter, ip_rate_limit
from app.shared.schemas import ItemList, item_list

wallet_router = APIRouter(prefix="/wallet", tags=["wallet"])
webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

#: A checkout calls the processor; a company opens only so many in an hour.
PURCHASES = RateLimitRule("credits.purchase:business", limit=10, window_sec=60 * 60)
#: Generous for the processor's retries, tight enough to blunt signature guessing.
WEBHOOKS_PER_IP = RateLimitRule("credits.webhook:ip", limit=120, window_sec=60)

IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=100)]


@wallet_router.get("", response_model=WalletRead, response_model_by_alias=True)
async def get_wallet(user: CurrentUser, db: DbSession) -> WalletRead:
    return await service.wallet_view(db, user)


@wallet_router.get("/ledger", response_model=LedgerPage, response_model_by_alias=True)
async def get_ledger(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> LedgerPage:
    total, rows = await service.list_ledger(db, user, limit=limit, offset=offset)
    return LedgerPage(total=total, items=[line_to_read(r) for r in rows])


@wallet_router.get("/plans", response_model=ItemList[PlanRead], response_model_by_alias=True)
async def get_plans(_: CurrentUser, db: DbSession) -> ItemList[PlanRead]:
    return item_list([plan_to_read(p) for p in await service.list_plans(db)])


@wallet_router.post("/purchases", response_model=PurchaseRead, response_model_by_alias=True, status_code=201)
async def create_purchase(
    payload: PurchaseCreate, user: CurrentUser, db: DbSession, idempotency_key: IdempotencyKeyHeader = None
) -> PurchaseRead:
    """Open a checkout. Credits arrive when the processor confirms payment
    by webhook, never from this response."""
    if not idempotency_key:
        raise BadRequest("Send an Idempotency-Key header so a retry cannot open a second order.")
    await get_limiter().check(PURCHASES, str(user.business_id))
    return await service.create_purchase(db, user, payload.plan_code, idempotency_key)


@webhooks_router.post(
    "/payments/{provider}",
    response_model=WebhookAck,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(WEBHOOKS_PER_IP))],
)
async def payment_webhook(provider: str, request: Request, db: DbSession) -> WebhookAck:
    """Public by design: the processor has no session. The signature over the
    raw body is the authentication; an unsigned or mis-signed call gets 401."""
    await service.handle_webhook(db, provider, await request.body(), request.headers)
    return WebhookAck()
