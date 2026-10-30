"""/admin/kyb/document-types — the per-country KYB document list.

Admins decide which documents each country offers and which are mandatory
for KYB submission. Types are never deleted (entries reference them): set
``active = false`` to hide one. Every change is written to
``admin_actions`` (``kyb_type.create`` / ``kyb_type.update``)."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import AdminEmail, parse_uuid
from app.models.kyb_document_type import KybDocumentType, KybInputKind
from app.modules.admin.service import record_action
from app.modules.auth.deps import DbSession
from app.modules.verification.schemas import DocTypeOut, doc_type_to_out
from app.shared.schemas import CamelModel, CountryCode, text

router = APIRouter(prefix="/kyb/document-types")

InputKind = Literal["value", "file", "value_or_file", "value_and_file"]
_CODE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_AADHAAR = re.compile(r"aadh?aa?r", re.IGNORECASE)
_EDITABLE = (
    "name", "input_kind", "value_pattern", "value_placeholder", "help_text",
    "is_mandatory", "is_unique", "sort_order", "active",
)


def _check_pattern(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    try:
        re.compile(v)
    except re.error as exc:
        raise ValueError(f"Invalid format pattern: {exc}") from None
    return v.strip()


def _no_aadhaar(v: str | None) -> str | None:
    if v and _AADHAAR.search(v):
        raise ValueError("Aadhaar can't be a KYB document (Aadhaar Act).")
    return v


class DocTypeAdminOut(DocTypeOut):
    is_unique: bool
    active: bool


class DocTypeCreate(CamelModel):
    country: CountryCode
    code: str = Field(min_length=2, max_length=40)
    name: text(150, 2)  # type: ignore[valid-type]
    input_kind: InputKind
    value_pattern: str | None = Field(None, max_length=200)
    value_placeholder: text(60) | None = None  # type: ignore[valid-type]
    help_text: text(300) | None = None  # type: ignore[valid-type]
    is_mandatory: bool = False
    is_unique: bool = True
    sort_order: int = Field(0, ge=0, le=9999)
    active: bool = True

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip().lower()
        if not _CODE.match(v):
            raise ValueError("Code: lower-case letters, digits and _ (start with a letter).")
        return _no_aadhaar(v)

    _pattern = field_validator("value_pattern")(classmethod(lambda cls, v: _check_pattern(v)))
    _name = field_validator("name")(classmethod(lambda cls, v: _no_aadhaar(v)))


class DocTypeUpdate(CamelModel):
    """Only sent fields change. Country and code are fixed once created."""

    name: text(150, 2) | None = None  # type: ignore[valid-type]
    input_kind: InputKind | None = None
    value_pattern: str | None = Field(None, max_length=200)
    value_placeholder: text(60) | None = None  # type: ignore[valid-type]
    help_text: text(300) | None = None  # type: ignore[valid-type]
    is_mandatory: bool | None = None
    is_unique: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=9999)
    active: bool | None = None

    _pattern = field_validator("value_pattern")(classmethod(lambda cls, v: _check_pattern(v)))
    _name = field_validator("name")(classmethod(lambda cls, v: _no_aadhaar(v)))


def _out(t: KybDocumentType) -> DocTypeAdminOut:
    return DocTypeAdminOut(**doc_type_to_out(t).model_dump(), is_unique=t.is_unique, active=t.active)


def _snapshot(t: KybDocumentType) -> dict:
    return {f: (getattr(t, f).value if f == "input_kind" else getattr(t, f)) for f in _EDITABLE}


@router.get("", response_model=list[DocTypeAdminOut], response_model_by_alias=True)
async def list_types(_: AdminEmail, db: DbSession, country: str | None = Query(None, min_length=2, max_length=2)) -> list[DocTypeAdminOut]:
    """All types (active and hidden), optionally for one country."""
    q = select(KybDocumentType).order_by(KybDocumentType.country, KybDocumentType.sort_order, KybDocumentType.name)
    if country:
        q = q.where(KybDocumentType.country == country.upper())
    return [_out(t) for t in await db.scalars(q)]


@router.post("", response_model=DocTypeAdminOut, response_model_by_alias=True, status_code=201)
async def create_type(payload: DocTypeCreate, admin: AdminEmail, db: DbSession) -> DocTypeAdminOut:
    t = KybDocumentType(**payload.model_dump(exclude={"input_kind"}), input_kind=KybInputKind(payload.input_kind))
    db.add(t)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict(f"{payload.country} already has a document type with code '{payload.code}'.") from None
    record_action(db, admin_email=admin, action="kyb_type.create", target_type="kyb_document_type",
                  target_id=t.id, details=_snapshot(t) | {"country": t.country, "code": t.code})
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.patch("/{type_id}", response_model=DocTypeAdminOut, response_model_by_alias=True)
async def update_type(type_id: str, payload: DocTypeUpdate, admin: AdminEmail, db: DbSession) -> DocTypeAdminOut:
    t = await db.get(KybDocumentType, parse_uuid(type_id)) if parse_uuid(type_id) else None
    if t is None:
        raise NotFound("Document type not found")
    before = _snapshot(t)
    sent = payload.model_fields_set
    if not sent:
        raise BadRequest("Nothing to change.")
    for field in sent:
        value = getattr(payload, field)
        if field == "input_kind" and value is not None:
            value = KybInputKind(value)
        if value is None and field in {"name", "input_kind", "is_mandatory", "is_unique", "sort_order", "active"}:
            raise BadRequest(f"{field} can't be empty.")
        setattr(t, field, value)
    after = _snapshot(t)
    changes = {k: {"from": before[k], "to": after[k]} for k in _EDITABLE if before[k] != after[k]}
    if changes:
        record_action(db, admin_email=admin, action="kyb_type.update", target_type="kyb_document_type",
                      target_id=t.id, details={"country": t.country, "code": t.code, "changes": changes})
    await db.commit()
    await db.refresh(t)
    return _out(t)
