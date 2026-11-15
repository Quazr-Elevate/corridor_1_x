"""/admin/listing-templates — what a listing in each category is asked for.

* ``/spec-parameters`` — the specification rows of a category (name, unit,
  MIN / MAX / EQ, required or not).
* ``/certificate-types`` — the documents a listing can carry, per category
  or for every category (``*``).

Rows are never deleted (listings reference them): set ``active = false`` to
retire one. Every change is written to ``admin_actions``."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import Conflict, NotFound
from app.core.security import parse_uuid
from app.models.listing import ALL_CATEGORIES, CertificateType, SpecParameter
from app.modules.admin.deps import CanManageCatalog, CanViewCatalog
from app.modules.admin.service import record_action
from app.modules.auth.deps import DbSession
from app.modules.catalog.schemas import Category, CertificateTypeOut, SpecParameterOut
from app.modules.catalog.service import certificate_type_out, spec_parameter_out
from app.shared.schemas import CamelModel, RequestModel, text

router = APIRouter(prefix="/listing-templates")

_CODE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
Operator = Literal["MIN", "MAX", "EQ"]
ValueType = Literal["number", "text"]


def _clean_code(v: str) -> str:
    v = v.strip().lower()
    if not _CODE.match(v):
        raise ValueError("Code: lower-case letters, digits and _ (start with a letter).")
    return v


class SpecParameterList(CamelModel):
    total: int
    items: list[SpecParameterOut]


class CertificateTypeList(CamelModel):
    total: int
    items: list[CertificateTypeOut]


class SpecParameterCreate(RequestModel):
    category: Category
    code: str = Field(min_length=2, max_length=40)
    name: text(100, 2)  # type: ignore[valid-type]
    value_type: ValueType = "number"
    unit: text(20) | None = None  # type: ignore[valid-type]
    default_operator: Operator = "MAX"
    test_method: text(100) | None = None  # type: ignore[valid-type]
    is_required: bool = False
    sort_order: int = Field(0, ge=0, le=9999)
    active: bool = True

    _code = field_validator("code")(classmethod(lambda cls, v: _clean_code(v)))


class SpecParameterPatch(RequestModel):
    """The category, code and value type are fixed once listings use the row."""

    name: text(100, 2) | None = None  # type: ignore[valid-type]
    unit: text(20) | None = None  # type: ignore[valid-type]
    default_operator: Operator | None = None
    test_method: text(100) | None = None  # type: ignore[valid-type]
    is_required: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=9999)
    active: bool | None = None


class CertificateTypeCreate(RequestModel):
    # A product category, or "*" for every category.
    category: Category | Literal["*"] = ALL_CATEGORIES
    code: str = Field(min_length=2, max_length=40)
    name: text(150, 2)  # type: ignore[valid-type]
    help_text: text(300) | None = None  # type: ignore[valid-type]
    is_required: bool = False
    sort_order: int = Field(0, ge=0, le=9999)
    active: bool = True

    _code = field_validator("code")(classmethod(lambda cls, v: _clean_code(v)))


class CertificateTypePatch(RequestModel):
    name: text(150, 2) | None = None  # type: ignore[valid-type]
    help_text: text(300) | None = None  # type: ignore[valid-type]
    is_required: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=9999)
    active: bool | None = None


_NOT_NULLABLE = ("name", "default_operator", "is_required", "sort_order", "active")


def _apply(row, payload: RequestModel) -> dict:
    """Write the fields the request sent; return ``{field: [before, after]}``."""
    changed = {}
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is None and field in _NOT_NULLABLE:
            continue
        if isinstance(value, str) and not value:
            value = None
        before = getattr(row, field)
        if before != value:
            setattr(row, field, value)
            changed[field] = [before, value]
    return changed


# ── Specification parameters ─────────────────────────────────────────


@router.get("/spec-parameters", response_model=SpecParameterList, response_model_by_alias=True)
async def list_spec_parameters(
    _: CanViewCatalog, db: DbSession, category: str | None = Query(None, max_length=50)
) -> SpecParameterList:
    """Every row (active and retired), optionally for one category."""
    stmt = select(SpecParameter)
    if category:
        stmt = stmt.where(SpecParameter.category == category)
    rows = list(await db.scalars(stmt.order_by(SpecParameter.category, SpecParameter.sort_order, SpecParameter.name)))
    return SpecParameterList(total=len(rows), items=[spec_parameter_out(r) for r in rows])


@router.post("/spec-parameters", response_model=SpecParameterOut, response_model_by_alias=True, status_code=201)
async def create_spec_parameter(payload: SpecParameterCreate, admin: CanManageCatalog, db: DbSession) -> SpecParameterOut:
    row = SpecParameter(**payload.model_dump())
    row.unit = row.unit or None
    row.test_method = row.test_method or None
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict(f"{payload.category} already has a specification with the code “{payload.code}”.") from None
    record_action(
        db, admin=admin, action="spec_parameter.create", target_type="spec_parameter", target_id=row.id,
        details={"category": row.category, "code": row.code},
    )
    await db.commit()
    await db.refresh(row)
    return spec_parameter_out(row)


@router.patch("/spec-parameters/{parameter_id}", response_model=SpecParameterOut, response_model_by_alias=True)
async def update_spec_parameter(
    parameter_id: str, payload: SpecParameterPatch, admin: CanManageCatalog, db: DbSession
) -> SpecParameterOut:
    pid = parse_uuid(parameter_id)
    row = await db.get(SpecParameter, pid) if pid else None
    if row is None:
        raise NotFound("Specification not found")
    changed = _apply(row, payload)
    if changed:
        record_action(
            db, admin=admin, action="spec_parameter.update", target_type="spec_parameter", target_id=row.id,
            details={"category": row.category, "code": row.code, "changed": changed},
        )
        await db.commit()
        await db.refresh(row)
    return spec_parameter_out(row)


# ── Certificate types ────────────────────────────────────────────────


@router.get("/certificate-types", response_model=CertificateTypeList, response_model_by_alias=True)
async def list_certificate_types(
    _: CanViewCatalog, db: DbSession, category: str | None = Query(None, max_length=50)
) -> CertificateTypeList:
    """Every type (active and retired); with ``category``, that category's
    own types plus the ones for every category."""
    stmt = select(CertificateType)
    if category:
        stmt = stmt.where(CertificateType.category.in_((category, ALL_CATEGORIES)))
    rows = list(await db.scalars(stmt.order_by(CertificateType.category, CertificateType.sort_order, CertificateType.name)))
    return CertificateTypeList(total=len(rows), items=[certificate_type_out(r) for r in rows])


@router.post("/certificate-types", response_model=CertificateTypeOut, response_model_by_alias=True, status_code=201)
async def create_certificate_type(
    payload: CertificateTypeCreate, admin: CanManageCatalog, db: DbSession
) -> CertificateTypeOut:
    row = CertificateType(**payload.model_dump())
    row.help_text = row.help_text or None
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict(f"A document type with the code “{payload.code}” already exists for that category.") from None
    record_action(
        db, admin=admin, action="certificate_type.create", target_type="certificate_type", target_id=row.id,
        details={"category": row.category, "code": row.code},
    )
    await db.commit()
    await db.refresh(row)
    return certificate_type_out(row)


@router.patch("/certificate-types/{type_id}", response_model=CertificateTypeOut, response_model_by_alias=True)
async def update_certificate_type(
    type_id: str, payload: CertificateTypePatch, admin: CanManageCatalog, db: DbSession
) -> CertificateTypeOut:
    tid = parse_uuid(type_id)
    row = await db.get(CertificateType, tid) if tid else None
    if row is None:
        raise NotFound("Document type not found")
    changed = _apply(row, payload)
    if changed:
        record_action(
            db, admin=admin, action="certificate_type.update", target_type="certificate_type", target_id=row.id,
            details={"category": row.category, "code": row.code, "changed": changed},
        )
        await db.commit()
        await db.refresh(row)
    return certificate_type_out(row)
