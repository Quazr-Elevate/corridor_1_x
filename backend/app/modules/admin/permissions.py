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
    listings_override = "listings.override"  # approve a listing the leak filter flagged, with a reason
    accounts_security = "accounts.security"  # unlock traders, sign them out
    admins_manage = "admins.manage"  # create / edit / unlock admin accounts
    rfqs_triage = "rfqs.triage"  # work the RFQ queue: matches, confirm, reject, hold
    margin_approve = "margin.approve"  # accept a cost sheet whose margin is under the floor
    trade_configure = "trade.configure"  # held countries and the desk's settings
    credits_manage = "credits.manage"  # set credit prices and plans
    identity_unmask = "identity.unmask"  # turn a company code back into a name, with a reason
    suspension_lift = "suspensions.lift"  # let a company suspended for leak strikes trade again (A-075)
    finance_view = "finance.view"  # the trade ledger and a deal's books (M5)
    ledger_correct = "ledger.correct"  # reverse a ledger posting (finance manager)
    statements_work = "statements.work"  # import bank statements, match or set aside lines (finance)
    bank_accounts_verify = "bank_accounts.verify"  # verify or reject a business's bank account (finance manager)
    bank_accounts_reveal = "bank_accounts.reveal"  # see a full account number and holder (finance manager, audited)
    documents_sign = "documents.sign"  # countersign LOIs and contracts for Corridor One X (A-081)
    templates_approve = "templates.approve"  # record a lawyer's approval of a template version (CX-108)
    samples_handle = "samples.handle"  # record a sample's hops at the hub: received, sealed, forwarded (CX-102)


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
TRADE_DESK = frozenset({Perm.dashboard_view, Perm.rfqs_triage, Perm.samples_handle})
#: A desk manager also approves what a desk user may not approve alone.
DESK_MANAGER = TRADE_DESK | {Perm.margin_approve, Perm.suspension_lift, Perm.documents_sign}

#: Finance works the books from company codes, like the desk (A-083).
FINANCE = frozenset({Perm.dashboard_view, Perm.finance_view, Perm.statements_work})
FINANCE_MANAGER = FINANCE | {Perm.ledger_correct, Perm.bank_accounts_verify, Perm.bank_accounts_reveal}
LOGISTICS = frozenset({Perm.dashboard_view})

ROLE_PERMISSIONS: dict[AdminRole, frozenset[Perm]] = {
    AdminRole.super_admin: frozenset(Perm),
    AdminRole.reviewer: REVIEWER,
    AdminRole.trade_desk: TRADE_DESK,
    AdminRole.desk_manager: DESK_MANAGER,
    AdminRole.finance: FINANCE,
    AdminRole.finance_manager: FINANCE_MANAGER,
    AdminRole.logistics: LOGISTICS,
}


def permissions_for(role: AdminRole) -> frozenset[Perm]:
    return ROLE_PERMISSIONS.get(role, frozenset())
