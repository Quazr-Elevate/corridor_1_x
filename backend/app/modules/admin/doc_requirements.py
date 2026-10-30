"""/admin/doc-requirements — CRUD on the per-country KYB document catalog.

Rows here drive the Documents tab on each business profile: for a
business in India, every active ``is_mandatory`` row for IN surfaces as
an upload slot that must be filled before the business can submit for
verification.

Rows are seeded through this screen, not through migrations. The admin
can list, add, edit (except ``country_code`` / ``slug`` — immutable to
avoid orphaning existing uploads), and soft-deactivate rows.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.security import AdminEmail, parse_uuid
from app.modules.admin import service
from app.modules.admin.schemas import DocRequirementIn, DocRequirementOut, DocRequirementUpdate
from app.modules.auth.deps import DbSession

router = APIRouter()


@router.get(
    "/doc-requirements",
    response_model=list[DocRequirementOut],
    response_model_by_alias=True,
)
async def list_doc_requirements(
    _: AdminEmail,
    db: DbSession,
    country: str | None = Query(None, min_length=2, max_length=2, description="ISO alpha-2 — filter by country"),
    include_inactive: bool = Query(False, description="Include soft-deactivated rows"),
) -> list[DocRequirementOut]:
    return await service.list_doc_requirements(db, country=country, include_inactive=include_inactive)


@router.post(
    "/doc-requirements",
    response_model=DocRequirementOut,
    response_model_by_alias=True,
    status_code=201,
)
async def create_doc_requirement(
    payload: DocRequirementIn, admin: AdminEmail, db: DbSession
) -> DocRequirementOut:
    return await service.create_doc_requirement(db, admin, payload)


@router.patch(
    "/doc-requirements/{req_id}",
    response_model=DocRequirementOut,
    response_model_by_alias=True,
)
async def update_doc_requirement(
    req_id: str, payload: DocRequirementUpdate, admin: AdminEmail, db: DbSession
) -> DocRequirementOut:
    return await service.update_doc_requirement(db, admin, parse_uuid(req_id), payload)
