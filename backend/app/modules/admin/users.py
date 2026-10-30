"""/admin/users/* — list, detail, edit, verify, reject.

URLs keep the user id; every action operates on that user's business."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query

from app import notifications
from app.core.security import AdminEmail, parse_uuid
from app.modules.admin import service
from app.modules.admin.schemas import StatusChanged, UserDetail, UserList, UserPatchIn, UserRejectIn
from app.modules.auth.deps import DbSession

router = APIRouter()


@router.get("/users", response_model=UserList, response_model_by_alias=True)
async def list_users(
    _: AdminEmail,
    db: DbSession,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> UserList:
    return await service.list_users(db, q=q, status=status, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=UserDetail, response_model_by_alias=True)
async def user_detail(user_id: str, _: AdminEmail, db: DbSession) -> UserDetail:
    return await service.user_detail(db, parse_uuid(user_id))


@router.patch("/users/{user_id}", response_model=UserDetail, response_model_by_alias=True)
async def update_user(user_id: str, payload: UserPatchIn, admin: AdminEmail, db: DbSession) -> UserDetail:
    uid = parse_uuid(user_id)
    await service.update_user(db, admin, uid, payload)
    return await service.user_detail(db, uid)


@router.post("/users/{user_id}/verify", response_model=StatusChanged, response_model_by_alias=True)
async def verify_user(user_id: str, admin: AdminEmail, db: DbSession, background: BackgroundTasks) -> StatusChanged:
    d = await service.verify_user(db, admin, parse_uuid(user_id))
    if d.email:
        background.add_task(
            notifications.deliver_safely,
            notifications.send_verification_approved,
            to=d.email,
            first_name=notifications.first_name_of(d.full_name),
        )
    return StatusChanged(user_id=str(d.user_id), business_id=str(d.business_id), status=d.status.value)


@router.post("/users/{user_id}/reject", response_model=StatusChanged, response_model_by_alias=True)
async def reject_user(
    user_id: str, payload: UserRejectIn, admin: AdminEmail, db: DbSession, background: BackgroundTasks
) -> StatusChanged:
    d = await service.reject_user(
        db, admin, parse_uuid(user_id), payload.reason, failed_items=payload.failed_items
    )
    if d.email:
        background.add_task(
            notifications.deliver_safely,
            notifications.send_verification_rejected,
            to=d.email,
            first_name=notifications.first_name_of(d.full_name),
            reason=payload.reason.strip(),
        )
    return StatusChanged(user_id=str(d.user_id), business_id=str(d.business_id), status=d.status.value)
