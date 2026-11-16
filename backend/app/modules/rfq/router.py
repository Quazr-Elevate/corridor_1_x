"""/rfqs — a buyer's own requests — and /matched-rfqs — what the desk has
matched to a seller."""
from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.rfq import service
from app.modules.rfq.schemas import (
    MatchedRfqList,
    RfqCreate,
    RfqList,
    RfqRead,
    RfqSellerView,
    RfqUpdate,
    SubmitCost,
)
from app.ratelimit import RateLimitRule, get_limiter

rfqs_router = APIRouter(prefix="/rfqs", tags=["rfqs"])
matched_router = APIRouter(prefix="/matched-rfqs", tags=["rfqs"])

#: Each submission goes to a person at the desk.
SUBMISSIONS = RateLimitRule("rfq.submit:business", limit=30, window_sec=60 * 60)
DRAFTS = RateLimitRule("rfq.create:business", limit=120, window_sec=60 * 60)


@rfqs_router.get("", response_model=RfqList, response_model_by_alias=True)
async def list_rfqs(
    user: CurrentUser, db: DbSession, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
) -> RfqList:
    total, rows = await service.list_own(db, user, limit=limit, offset=offset)
    return RfqList(total=total, items=[await service.to_read(db, r) for r in rows])


@rfqs_router.post("", response_model=RfqRead, response_model_by_alias=True, status_code=201)
async def create_rfq(payload: RfqCreate, user: CurrentUser, db: DbSession) -> RfqRead:
    """Start a draft. Any signed-in business may draft; submitting needs verification."""
    await get_limiter().check(DRAFTS, str(user.business_id))
    return await service.to_read(db, await service.create_rfq(db, user, payload))


@rfqs_router.get("/submit-cost", response_model=SubmitCost, response_model_by_alias=True)
async def submit_cost(user: CurrentUser, db: DbSession) -> SubmitCost:
    return await service.submit_cost(db, user)


@rfqs_router.get("/{rfq_id}", response_model=RfqRead, response_model_by_alias=True)
async def get_rfq(rfq_id: str, user: CurrentUser, db: DbSession) -> RfqRead:
    return await service.to_read(db, await service.get_own(db, user, parse_uuid(rfq_id)))


@rfqs_router.patch("/{rfq_id}", response_model=RfqRead, response_model_by_alias=True)
async def update_rfq(rfq_id: str, payload: RfqUpdate, user: CurrentUser, db: DbSession) -> RfqRead:
    return await service.to_read(db, await service.update_rfq(db, user, parse_uuid(rfq_id), payload))


@rfqs_router.delete("/{rfq_id}", status_code=204, response_class=Response)
async def delete_rfq(rfq_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_draft(db, user, parse_uuid(rfq_id))
    return Response(status_code=204)


@rfqs_router.get("/{rfq_id}/seller-preview", response_model=RfqSellerView, response_model_by_alias=True)
async def seller_preview(rfq_id: str, user: CurrentUser, db: DbSession) -> RfqSellerView:
    """Exactly what a matched seller will read, before the buyer submits."""
    return await service.seller_view(db, await service.get_own(db, user, parse_uuid(rfq_id)))


@rfqs_router.post("/{rfq_id}/submit", response_model=RfqRead, response_model_by_alias=True)
async def submit_rfq(rfq_id: str, user: CurrentUser, db: DbSession) -> RfqRead:
    """Send a draft to the desk. Takes a free RFQ or the RFQ_POST credits."""
    await get_limiter().check(SUBMISSIONS, str(user.business_id))
    return await service.to_read(db, await service.submit_rfq(db, user, parse_uuid(rfq_id)))


@matched_router.get("", response_model=MatchedRfqList, response_model_by_alias=True)
async def list_matched(
    user: CurrentUser, db: DbSession, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
) -> MatchedRfqList:
    total, rows = await service.list_matched(db, user, limit=limit, offset=offset)
    return MatchedRfqList(total=total, items=rows)


@matched_router.post("/{rfq_id}/open", response_model=RfqSellerView, response_model_by_alias=True)
async def open_matched(rfq_id: str, user: CurrentUser, db: DbSession) -> RfqSellerView:
    """Read a matched RFQ in full. POST because the first opening spends
    credits (RFQ_VIEW); opening it again is free."""
    return await service.open_matched(db, user, parse_uuid(rfq_id))
