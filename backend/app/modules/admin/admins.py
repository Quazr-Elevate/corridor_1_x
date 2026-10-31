"""/admin/admins/* — super admins manage admin accounts; plus trader
account security (unlock / sign out) under /admin/users/{id}/…"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.security import parse_uuid
from app.core.time import utcnow
from app.models.admin_user import AdminRole, AdminStatus, AdminUser
from app.modules.admin import accounts
from app.modules.admin.deps import CanManageAccountSecurity, CanManageAdmins
from app.modules.admin.schemas import AdminAccountOut, AdminCreateIn, AdminPatchIn, AdminWithPassword
from app.modules.auth.deps import DbSession
from app.modules.auth.lockout import lock_state
from app.modules.auth.schemas import OkResponse

router = APIRouter()


def _out(a: AdminUser) -> AdminAccountOut:
    return AdminAccountOut(
        id=str(a.id), email=a.email, full_name=a.full_name, role=a.role.value, status=a.status.value,
        must_change_password=a.must_change_password, lock_state=lock_state(a, utcnow()),
        last_login_at=a.last_login_at, created_by=a.created_by, created_at=a.created_at,
    )


@router.get("/admins", response_model=list[AdminAccountOut], response_model_by_alias=True)
async def list_admins(_: CanManageAdmins, db: DbSession) -> list[AdminAccountOut]:
    return [_out(a) for a in await accounts.list_admins(db)]


@router.post("/admins", response_model=AdminWithPassword, response_model_by_alias=True, status_code=201)
async def create_admin(payload: AdminCreateIn, actor: CanManageAdmins, db: DbSession) -> AdminWithPassword:
    admin, password = await accounts.create_admin(
        db, actor, email=payload.email, full_name=payload.full_name, role=AdminRole(payload.role)
    )
    return AdminWithPassword(admin=_out(admin), temporary_password=password)


@router.patch("/admins/{admin_id}", response_model=AdminAccountOut, response_model_by_alias=True)
async def update_admin(admin_id: str, payload: AdminPatchIn, actor: CanManageAdmins, db: DbSession) -> AdminAccountOut:
    admin = await accounts.update_admin(
        db, actor, parse_uuid(admin_id),
        full_name=payload.full_name,
        role=AdminRole(payload.role) if payload.role else None,
        status=AdminStatus(payload.status) if payload.status else None,
    )
    return _out(admin)


@router.post("/admins/{admin_id}/reset-password", response_model=AdminWithPassword, response_model_by_alias=True)
async def reset_admin_password(admin_id: str, actor: CanManageAdmins, db: DbSession) -> AdminWithPassword:
    admin, password = await accounts.reset_admin_password(db, actor, parse_uuid(admin_id))
    return AdminWithPassword(admin=_out(admin), temporary_password=password)


@router.post("/admins/{admin_id}/unlock", response_model=AdminAccountOut, response_model_by_alias=True)
async def unlock_admin(admin_id: str, actor: CanManageAdmins, db: DbSession) -> AdminAccountOut:
    return _out(await accounts.unlock_admin(db, actor, parse_uuid(admin_id)))


@router.post("/admins/{admin_id}/sign-out", response_model=OkResponse, response_model_by_alias=True)
async def sign_out_admin(admin_id: str, actor: CanManageAdmins, db: DbSession) -> OkResponse:
    await accounts.sign_out_admin(db, actor, parse_uuid(admin_id))
    return OkResponse()


# ── Trader account security ──────────────────────────────────────────


@router.post("/users/{user_id}/unlock", response_model=OkResponse, response_model_by_alias=True)
async def unlock_user(user_id: str, actor: CanManageAccountSecurity, db: DbSession) -> OkResponse:
    await accounts.unlock_user(db, actor, parse_uuid(user_id))
    return OkResponse()


@router.post("/users/{user_id}/sign-out", response_model=OkResponse, response_model_by_alias=True)
async def sign_out_user(user_id: str, actor: CanManageAccountSecurity, db: DbSession) -> OkResponse:
    await accounts.sign_out_user(db, actor, parse_uuid(user_id))
    return OkResponse()
