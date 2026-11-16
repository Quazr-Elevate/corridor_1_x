"""/admin/dashboard/* and /admin/verify/queue."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.modules.admin import service
from app.modules.admin.schemas import DashboardStats, StuckUser, TimelinePoint, VerifyQueueRow
from app.modules.auth.deps import DbSession
from app.modules.admin.deps import CanReviewKyb, CanViewDashboard
from app.shared.schemas import ItemList, item_list

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats, response_model_by_alias=True)
async def dashboard_stats(_: CanViewDashboard, db: DbSession) -> DashboardStats:
    return await service.dashboard_stats(db)


@router.get("/dashboard/timeline", response_model=list[TimelinePoint], response_model_by_alias=True)
async def dashboard_timeline(_: CanViewDashboard, db: DbSession, days: int = Query(30, ge=1, le=180)) -> list[TimelinePoint]:
    return await service.dashboard_timeline(db, days)


@router.get("/dashboard/stuck", response_model=ItemList[StuckUser], response_model_by_alias=True)
async def dashboard_stuck(
    admin: CanViewDashboard, db: DbSession, limit: int = Query(10, ge=1, le=100)
) -> ItemList[StuckUser]:
    return item_list(await service.stuck_users(db, admin, limit))


@router.get("/verify/queue", response_model=ItemList[VerifyQueueRow], response_model_by_alias=True)
async def verify_queue(admin: CanReviewKyb, db: DbSession) -> ItemList[VerifyQueueRow]:
    return item_list(await service.verify_queue(db, admin))
