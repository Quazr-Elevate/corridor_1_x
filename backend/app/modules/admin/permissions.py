"""Admin roles → permissions (deny by default).

Every admin route depends on :func:`app.modules.admin.deps.require` with
one permission; ``tests/test_admin_permissions.py`` fails if a route under
``/admin`` has none. Add a role by adding a row to ``ROLE_PERMISSIONS``.
"""
from __future__ import annotations

import enum

from app.models.admin_user import AdminRole


class Perm(str, enum.Enum):
    dashboard_view = "dashboard.view"
    users_view = "users.view"
    users_edit = "users.edit"  # edit a business's profile fields
    kyb_review = "kyb.review"  # verify / reject businesses and documents
    kyb_sensitive_view = "kyb.sensitive_view"  # reveal full numbers, open files
    catalog_view = "catalog.view"  # countries + document types (read)
    catalog_manage = "catalog.manage"  # create / edit countries, document types, listing templates
    listings_review = "listings.review"  # approve / reject listings, set certificate visibility
    accounts_security = "accounts.security"  # unlock traders, sign them out
    admins_manage = "admins.manage"  # create / edit / unlock admin accounts
    rfqs_triage = "rfqs.triage"  # work the RFQ queue: matches, confirm, reject, hold
    trade_configure = "trade.configure"  # held countries and the desk's settings
    credits_manage = "credits.manage"  # set credit prices and plans
    identity_unmask = "identity.unmask"  # turn a company code back into a name, with a reason


REVIEWER = frozenset({
    Perm.dashboard_view,
    Perm.users_view,
    Perm.users_edit,
    Perm.kyb_review,
    Perm.kyb_sensitive_view,
    Perm.catalog_view,
    Perm.listings_review,
})

#: The trade desk works deals from company codes; it has no KYB or
#: directory access, so it cannot read a name without ``identity.unmask``.
TRADE_DESK = frozenset({Perm.dashboard_view, Perm.rfqs_triage})
#: A desk manager also approves what a desk user may not approve alone.
DESK_MANAGER = TRADE_DESK

ROLE_PERMISSIONS: dict[AdminRole, frozenset[Perm]] = {
    AdminRole.super_admin: frozenset(Perm),
    AdminRole.reviewer: REVIEWER,
    AdminRole.trade_desk: TRADE_DESK,
    AdminRole.desk_manager: DESK_MANAGER,
}


def permissions_for(role: AdminRole) -> frozenset[Perm]:
    return ROLE_PERMISSIONS.get(role, frozenset())
