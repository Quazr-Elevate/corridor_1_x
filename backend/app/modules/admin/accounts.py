"""Admin accounts: sign-in (with lockout), bootstrap, password changes, and
super-admin management of other admins. No FastAPI imports."""
from __future__ import annotations

import functools
import logging
import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound, Unauthorized
from app.core.security import hash_password, temporary_password, verify_password
from app.core.time import utcnow
from app.models.admin_user import AdminRole, AdminStatus, AdminUser
from app.models.user import User
from app.modules.admin.service import Actor, record_action
from app.modules.auth import lockout, sessions
from app.modules.auth.sessions import ClientInfo, record_event

log = logging.getLogger("app.admin")

INVALID = "Invalid credentials"


@functools.cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_hex(8))


def _norm(email: str) -> str:
    return email.strip().lower()


async def _bootstrap(db: AsyncSession, email: str, password: str) -> AdminUser | None:
    """While ``admin_users`` is empty, the env credentials create the first
    super admin (then the env password is no longer used)."""
    if await db.scalar(select(func.count()).select_from(AdminUser)):
        return None
    if not settings.admin_password_hash or email != _norm(settings.admin_email):
        return None
    if not verify_password(password, settings.admin_password_hash):
        return None
    admin = AdminUser(
        email=email,
        full_name="Super admin",
        role=AdminRole.super_admin,
        password_hash=settings.admin_password_hash,
        created_by="bootstrap",
    )
    db.add(admin)
    await db.flush()
    log.warning("admin_bootstrapped admin_id=%s", admin.id)
    return admin


async def authenticate(db: AsyncSession, *, email: str, password: str, client: ClientInfo) -> AdminUser:
    email = _norm(email)
    admin = await db.scalar(select(AdminUser).where(AdminUser.email == email))
    if admin is None:
        admin = await _bootstrap(db, email, password)
        if admin is None:
            verify_password(password, _dummy_hash())
            record_event(db, subject_type="admin", subject_id=None, event="login_failed", client=client,
                         details={"reason": "unknown_email"})
            await db.commit()
            raise Unauthorized(INVALID)
    else:
        now = utcnow()
        lockout.ensure_not_locked(admin, now)
        if not verify_password(password, admin.password_hash):
            locked = lockout.record_failure(admin, now)
            record_event(db, subject_type="admin", subject_id=admin.id, event="login_failed", client=client)
            if locked:
                record_event(db, subject_type="admin", subject_id=admin.id, event=locked, client=client)
                if locked == "locked_support":
                    log.warning("admin_locked_support admin_id=%s", admin.id)
            await db.commit()
            if locked:
                lockout.ensure_not_locked(admin, now)
            raise Unauthorized(INVALID)
    if admin.status != AdminStatus.active:
        raise Unauthorized(INVALID)
    lockout.record_success(admin)
    admin.last_login_at = utcnow()
    record_event(db, subject_type="admin", subject_id=admin.id, event="login_succeeded", client=client)
    return admin


async def change_own_password(
    db: AsyncSession, admin_id: uuid.UUID, *, current: str, new: str, keep_session: uuid.UUID, client: ClientInfo
) -> AdminUser:
    admin = await db.get(AdminUser, admin_id)
    if admin is None:
        raise Unauthorized("Not signed in")
    if not verify_password(current, admin.password_hash):
        raise Unauthorized("Current password is incorrect.")
    if new == current:
        raise BadRequest("New password must be different from the current one.")
    admin.password_hash = hash_password(new)
    admin.must_change_password = False
    admin.password_changed_at = utcnow()
    await sessions.revoke_all(db, sessions.admin_policy(), admin.id, "password_changed", keep=keep_session)
    record_event(db, subject_type="admin", subject_id=admin.id, event="password_changed", client=client)
    await db.commit()
    return admin


# ── Management (super admin) ─────────────────────────────────────────


async def list_admins(db: AsyncSession) -> list[AdminUser]:
    return list(await db.scalars(select(AdminUser).order_by(AdminUser.created_at.asc())))


async def _get(db: AsyncSession, admin_id: uuid.UUID | None) -> AdminUser:
    row = await db.get(AdminUser, admin_id) if admin_id else None
    if row is None:
        raise NotFound("Admin not found")
    return row


async def create_admin(db: AsyncSession, actor: Actor, *, email: str, full_name: str, role: AdminRole) -> tuple[AdminUser, str]:
    """New admin with a temporary password (shown once to the creator;
    must be changed at first sign-in)."""
    password = temporary_password()
    admin = AdminUser(
        email=_norm(email),
        full_name=full_name.strip(),
        role=role,
        password_hash=hash_password(password),
        must_change_password=True,
        created_by=actor.email,
    )
    db.add(admin)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict("An admin with this email already exists.") from None
    record_action(db, admin=actor, action="admin.create", target_type="admin_user", target_id=admin.id,
                  details={"role": role.value})
    await db.commit()
    return admin, password


async def _active_super_admins(db: AsyncSession) -> int:
    return await db.scalar(
        select(func.count()).select_from(AdminUser).where(
            AdminUser.role == AdminRole.super_admin, AdminUser.status == AdminStatus.active
        )
    ) or 0


async def update_admin(
    db: AsyncSession, actor: Actor, admin_id: uuid.UUID | None, *,
    full_name: str | None, role: AdminRole | None, status: AdminStatus | None,
) -> AdminUser:
    admin = await _get(db, admin_id)
    changes: dict[str, str] = {}
    if admin.id == actor.id and ((role and role != admin.role) or (status and status != admin.status)):
        raise BadRequest("You can't change your own role or status.")
    losing_super = admin.role == AdminRole.super_admin and admin.status == AdminStatus.active and (
        (role is not None and role != AdminRole.super_admin) or status == AdminStatus.disabled
    )
    if losing_super and await _active_super_admins(db) <= 1:
        raise BadRequest("Keep at least one active super admin.")
    if full_name is not None and full_name.strip() != admin.full_name:
        admin.full_name = full_name.strip()
        changes["fullName"] = "updated"
    if role is not None and role != admin.role:
        changes["role"] = f"{admin.role.value}→{role.value}"
        admin.role = role
    if status is not None and status != admin.status:
        changes["status"] = f"{admin.status.value}→{status.value}"
        admin.status = status
        if status == AdminStatus.disabled:
            await sessions.revoke_all(db, sessions.admin_policy(), admin.id, "account_disabled")
    if changes:
        record_action(db, admin=actor, action="admin.update", target_type="admin_user", target_id=admin.id,
                      details=changes)
        await db.commit()
    return admin


async def reset_admin_password(db: AsyncSession, actor: Actor, admin_id: uuid.UUID | None) -> tuple[AdminUser, str]:
    """New temporary password; signs the admin out and clears any lockout."""
    admin = await _get(db, admin_id)
    if admin.id == actor.id:
        raise BadRequest("Use 'Change password' for your own account.")
    password = temporary_password()
    admin.password_hash = hash_password(password)
    admin.must_change_password = True
    lockout.unlock(admin)
    await sessions.revoke_all(db, sessions.admin_policy(), admin.id, "password_reset")
    record_action(db, admin=actor, action="admin.password_reset", target_type="admin_user", target_id=admin.id)
    await db.commit()
    return admin, password


async def unlock_admin(db: AsyncSession, actor: Actor, admin_id: uuid.UUID | None) -> AdminUser:
    admin = await _get(db, admin_id)
    lockout.unlock(admin)
    record_event(db, subject_type="admin", subject_id=admin.id, event="unlocked", details={"by": actor.email})
    record_action(db, admin=actor, action="admin.unlock", target_type="admin_user", target_id=admin.id)
    await db.commit()
    return admin


async def sign_out_admin(db: AsyncSession, actor: Actor, admin_id: uuid.UUID | None) -> None:
    admin = await _get(db, admin_id)
    n = await sessions.revoke_all(db, sessions.admin_policy(), admin.id, "admin_revoked")
    record_action(db, admin=actor, action="admin.sign_out", target_type="admin_user", target_id=admin.id,
                  details={"sessions": n})
    await db.commit()


# ── Trader account security (support) ────────────────────────────────


async def unlock_user(db: AsyncSession, actor: Actor, user_id: uuid.UUID | None) -> None:
    user = await db.get(User, user_id) if user_id else None
    if user is None or user.deleted_at is not None:
        raise NotFound("User not found")
    lockout.unlock(user)
    record_event(db, subject_type="user", subject_id=user.id, event="unlocked", details={"by": actor.email})
    record_action(db, admin=actor, action="user.unlock", target_type="user", target_id=user.id)
    await db.commit()


async def sign_out_user(db: AsyncSession, actor: Actor, user_id: uuid.UUID | None) -> int:
    user = await db.get(User, user_id) if user_id else None
    if user is None or user.deleted_at is not None:
        raise NotFound("User not found")
    n = await sessions.revoke_all(db, sessions.user_policy(), user.id, "admin_revoked")
    record_event(db, subject_type="user", subject_id=user.id, event="sessions_revoked", details={"by": actor.email})
    record_action(db, admin=actor, action="user.sign_out", target_type="user", target_id=user.id,
                  details={"sessions": n})
    await db.commit()
    return n
