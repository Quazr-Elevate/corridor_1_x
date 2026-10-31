"""Admin request authentication + authorization.

``require(Perm.x)`` → dependency that resolves the ``cor1x_admin`` session
(server-side, ``admin_sessions``), checks the IP allowlist, the account
status, the temporary-password gate and the permission, and returns the
:class:`AdminPrincipal`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.logging import set_actor
from app.core.security import ADMIN_COOKIE, ip_allowed
from app.models.admin_user import AdminRole, AdminStatus, AdminUser
from app.modules.admin.permissions import Perm, permissions_for
from app.modules.auth.sessions import admin_policy, client_info, resolve_session


@dataclass(frozen=True)
class AdminPrincipal:
    id: uuid.UUID
    email: str
    full_name: str
    role: AdminRole
    session_id: uuid.UUID
    must_change_password: bool

    @property
    def permissions(self) -> frozenset[Perm]:
        return permissions_for(self.role)


def ensure_ip_allowed(request: Request) -> None:
    if not ip_allowed(client_info(request).ip, settings.admin_ip_allowlist_entries):
        raise Forbidden("The admin console isn't available from this network.")


async def _principal(request: Request, db: AsyncSession, token: str | None) -> AdminPrincipal:
    ensure_ip_allowed(request)
    session = await resolve_session(db, admin_policy(), token)
    if session is None:
        raise Unauthorized("Not signed in")
    admin = await db.get(AdminUser, session.admin_user_id)
    if admin is None or admin.status != AdminStatus.active:
        raise Unauthorized("Not signed in")
    set_actor("admin", admin.id)
    return AdminPrincipal(
        id=admin.id, email=admin.email, full_name=admin.full_name, role=admin.role,
        session_id=session.id, must_change_password=admin.must_change_password,
    )


def require(perm: Perm | None):
    """Dependency factory. ``None`` = any signed-in admin, allowed even with
    a temporary password (``/admin/me``, ``/admin/change-password``)."""

    async def _dep(
        request: Request,
        cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
        db: AsyncSession = Depends(get_db),
    ) -> AdminPrincipal:
        principal = await _principal(request, db, cor1x_admin)
        if perm is None:
            return principal
        if principal.must_change_password:
            raise Forbidden("Change your temporary password first.")
        if perm not in principal.permissions:
            raise Forbidden("Your admin role doesn't allow this.")
        return principal

    _dep.permission = perm  # type: ignore[attr-defined]  # read by the route-matrix test
    _dep.__name__ = f"require_{perm.value.replace('.', '_') if perm else 'signed_in'}"
    return _dep


SignedInAdmin = Annotated[AdminPrincipal, Depends(require(None))]
CanViewDashboard = Annotated[AdminPrincipal, Depends(require(Perm.dashboard_view))]
CanViewUsers = Annotated[AdminPrincipal, Depends(require(Perm.users_view))]
CanEditUsers = Annotated[AdminPrincipal, Depends(require(Perm.users_edit))]
CanReviewKyb = Annotated[AdminPrincipal, Depends(require(Perm.kyb_review))]
CanViewSensitive = Annotated[AdminPrincipal, Depends(require(Perm.kyb_sensitive_view))]
CanViewCatalog = Annotated[AdminPrincipal, Depends(require(Perm.catalog_view))]
CanManageCatalog = Annotated[AdminPrincipal, Depends(require(Perm.catalog_manage))]
CanManageAccountSecurity = Annotated[AdminPrincipal, Depends(require(Perm.accounts_security))]
CanManageAdmins = Annotated[AdminPrincipal, Depends(require(Perm.admins_manage))]
