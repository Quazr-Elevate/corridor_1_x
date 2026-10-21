"""/admin/dashboard/* and /admin/verify/queue."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.security import AdminEmail
from app.modules.admin import service
from app.modules.admin.schemas import DashboardStats, StuckUser, TimelinePoint, VerifyQueueRow
from app.modules.auth.deps import DbSession

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats, response_model_by_alias=True)
async def dashboard_stats(_: AdminEmail, db: DbSession) -> DashboardStats:
    return await service.dashboard_stats(db)


@router.get("/dashboard/timeline", response_model=list[TimelinePoint], response_model_by_alias=True)
async def dashboard_timeline(_: AdminEmail, db: DbSession, days: int = Query(30, ge=1, le=180)) -> list[TimelinePoint]:
    return await service.dashboard_timeline(db, days)


@router.get("/dashboard/stuck", response_model=list[StuckUser], response_model_by_alias=True)
async def dashboard_stuck(_: AdminEmail, db: DbSession, limit: int = Query(10, ge=1, le=100)) -> list[StuckUser]:
    return await service.stuck_users(db, limit)


@router.get("/verify/queue", response_model=list[VerifyQueueRow], response_model_by_alias=True)
async def verify_queue(_: AdminEmail, db: DbSession) -> list[VerifyQueueRow]:
    return await service.verify_queue(db)
