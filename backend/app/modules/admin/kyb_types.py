"""/admin/kyb — the per-country KYB document list.

* ``POST /admin/kyb/countries`` — add a country **together with** its
  documents; at least one must be required (one transaction).
* ``/admin/kyb/document-types`` — list / add to an existing country / edit.

Invariant: every set-up country keeps at least one active, required
document — the last one can't be hidden or made optional. Businesses can
only pick set-up countries. Types are never deleted (entries reference
them): set ``active = false`` to hide one. Every change is written to
``admin_actions`` (``kyb_country.create`` / ``kyb_type.create`` /
``kyb_type.update``)."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import parse_uuid
from app.models.country import Country
from app.models.exchange_rate import SUPPORTED_CURRENCIES
from app.models.kyb_document_type import KybDocumentType, KybInputKind
from app.modules.admin.service import record_action
from app.modules.auth.deps import DbSession
from app.modules.verification.schemas import CountryOut, DocTypeOut, country_to_out, doc_type_to_out
from app.modules.verification.seed import COUNTRY_REFERENCE
from app.shared.schemas import CamelModel, CountryCode, text
from app.modules.admin.deps import CanManageCatalog, CanViewCatalog

router = APIRouter(prefix="/kyb/document-types")
countries_router = APIRouter(prefix="/kyb/countries")

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


def _clean_code(v: str) -> str:
    v = v.strip().lower()
    if not _CODE.match(v):
        raise ValueError("Code: lower-case letters, digits and _ (start with a letter).")
    return _no_aadhaar(v)


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

    _code = field_validator("code")(classmethod(lambda cls, v: _clean_code(v)))

    _pattern = field_validator("value_pattern")(classmethod(lambda cls, v: _check_pattern(v)))
    _name = field_validator("name")(classmethod(lambda cls, v: _no_aadhaar(v)))


class CountryDocType(CamelModel):
    """A document entered while adding a country (country comes from the parent)."""

    code: str = Field(min_length=2, max_length=40)
    name: text(150, 2)  # type: ignore[valid-type]
    input_kind: InputKind
    value_pattern: str | None = Field(None, max_length=200)
    value_placeholder: text(60) | None = None  # type: ignore[valid-type]
    help_text: text(300) | None = None  # type: ignore[valid-type]
    is_mandatory: bool = True
    is_unique: bool = True
    sort_order: int = Field(0, ge=0, le=9999)

    _code = field_validator("code")(classmethod(lambda cls, v: _clean_code(v)))
    _pattern = field_validator("value_pattern")(classmethod(lambda cls, v: _check_pattern(v)))
    _name = field_validator("name")(classmethod(lambda cls, v: _no_aadhaar(v)))


Currency = Literal["INR", "AED", "USD"]
_COUNTRY_FIELDS = ("name", "flag", "dial_code", "default_currency", "region_label", "postal_label", "postal_pattern")


def _check_dial(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip()
    if not re.fullmatch(r"\+[0-9]{1,4}", v):
        raise ValueError("Dial code looks like +91.")
    return v


class CountryFields(CamelModel):
    """Country details. Omitted fields fall back to the built-in reference
    for known countries; ``name`` is required for others."""

    name: text(100, 2) | None = None  # type: ignore[valid-type]
    flag: text(8) | None = None  # type: ignore[valid-type]
    dial_code: str | None = Field(None, max_length=6)
    default_currency: Currency | None = None
    region_label: text(30, 2) | None = None  # type: ignore[valid-type]
    postal_label: text(30, 2) | None = None  # type: ignore[valid-type]
    postal_pattern: str | None = Field(None, max_length=100)

    _dial = field_validator("dial_code")(classmethod(lambda cls, v: _check_dial(v)))
    _postal = field_validator("postal_pattern")(classmethod(lambda cls, v: _check_pattern(v)))


class CountryCreate(CountryFields):
    country: CountryCode
    documents: list[CountryDocType] = Field(min_length=1, max_length=40)

    @field_validator("documents")
    @classmethod
    def _rules(cls, docs: list[CountryDocType]) -> list[CountryDocType]:
        if not any(d.is_mandatory for d in docs):
            raise ValueError("Mark at least one document as required for this country.")
        codes = [d.code for d in docs]
        if len(set(codes)) != len(codes):
            raise ValueError("Each document needs its own code.")
        return docs


class CountryUpdate(CountryFields):
    """Only sent fields change; ``active`` pauses / resumes onboarding."""

    active: bool | None = None


class CountryAdminOut(CountryOut):
    active: bool
    documents: int
    required_documents: int
    businesses: int


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
async def list_types(_: CanViewCatalog, db: DbSession, country: str | None = Query(None, min_length=2, max_length=2)) -> list[DocTypeAdminOut]:
    """All types (active and hidden), optionally for one country."""
    q = select(KybDocumentType).order_by(KybDocumentType.country, KybDocumentType.sort_order, KybDocumentType.name)
    if country:
        q = q.where(KybDocumentType.country == country.upper())
    return [_out(t) for t in await db.scalars(q)]


def _country_snapshot(c: Country) -> dict:
    return {f: getattr(c, f) for f in (*_COUNTRY_FIELDS, "active")}


async def _country_out(db, c: Country) -> CountryAdminOut:
    from app.models.business import Business

    types = list(await db.scalars(select(KybDocumentType).where(KybDocumentType.country == c.code)))
    n_biz = len(list(await db.scalars(
        select(Business.id).where(Business.country == c.code, Business.deleted_at.is_(None))
    )))
    return CountryAdminOut(
        **country_to_out(c).model_dump(),
        active=c.active,
        documents=sum(1 for t in types if t.active),
        required_documents=sum(1 for t in types if t.active and t.is_mandatory),
        businesses=n_biz,
    )


@countries_router.get("", response_model=list[CountryAdminOut], response_model_by_alias=True)
async def list_countries(_: CanViewCatalog, db: DbSession) -> list[CountryAdminOut]:
    """Every country (open and paused) with document and business counts."""
    return [await _country_out(db, c) for c in await db.scalars(select(Country).order_by(Country.name))]


@countries_router.patch("/{code}", response_model=CountryAdminOut, response_model_by_alias=True)
async def update_country(code: str, payload: CountryUpdate, admin: CanManageCatalog, db: DbSession) -> CountryAdminOut:
    """Edit details, or pause / resume onboarding (``active``)."""
    c = await db.get(Country, code.upper()[:2])
    if c is None:
        raise NotFound("Country not found")
    sent = payload.model_fields_set
    if not sent:
        raise BadRequest("Nothing to change.")
    before = _country_snapshot(c)
    for field in sent:
        value = getattr(payload, field)
        if value is None and field in {"name", "default_currency", "region_label", "postal_label", "active"}:
            raise BadRequest(f"{field} can't be empty.")
        setattr(c, field, value)
    c.updated_by = admin.email
    after = _country_snapshot(c)
    changes = {k: {"from": before[k], "to": after[k]} for k in after if before[k] != after[k]}
    if changes:
        record_action(db, admin=admin, action="kyb_country.update", target_type="country", target_id=c.code,
                      details={"changes": changes})
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise Conflict("Another country already has that name.") from None
    await db.refresh(c)
    return await _country_out(db, c)


async def _country_exists(db, country: str) -> bool:
    return (
        await db.scalar(select(KybDocumentType.id).where(KybDocumentType.country == country.upper()).limit(1))
    ) is not None


async def _other_required_count(db, t: KybDocumentType) -> int:
    rows = await db.scalars(
        select(KybDocumentType.id).where(
            KybDocumentType.country == t.country,
            KybDocumentType.id != t.id,
            KybDocumentType.is_mandatory.is_(True),
            KybDocumentType.active.is_(True),
        )
    )
    return len(list(rows))


@countries_router.post("", response_model=list[DocTypeAdminOut], response_model_by_alias=True, status_code=201)
async def create_country(payload: CountryCreate, admin: CanManageCatalog, db: DbSession) -> list[DocTypeAdminOut]:
    """Add a country **with** its documents in one go (≥ 1 required).

    A country row left over from old data (no documents yet) is reused and
    completed; a country that already has documents is refused."""
    if await _country_exists(db, payload.country):
        raise Conflict(f"{payload.country} is already set up — add documents to it instead.")
    ref = COUNTRY_REFERENCE.get(payload.country)
    defaults = dict(zip(_COUNTRY_FIELDS, ref)) if ref else {}
    fields = {f: getattr(payload, f) if getattr(payload, f) is not None else defaults.get(f) for f in _COUNTRY_FIELDS}
    if not fields["name"]:
        raise BadRequest("Enter the country's name.")
    fields["default_currency"] = fields["default_currency"] or "USD"
    fields["region_label"] = fields["region_label"] or "State / region"
    fields["postal_label"] = fields["postal_label"] or "Postal code"
    if fields["default_currency"] not in SUPPORTED_CURRENCIES:
        raise BadRequest("Unsupported currency.")
    country = await db.get(Country, payload.country)
    if country is None:
        country = Country(code=payload.country, created_by=admin.email, updated_by=admin.email, active=True, **fields)
        db.add(country)
    else:
        for f, v in fields.items():
            setattr(country, f, v)
        country.active = True
        country.updated_by = admin.email
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict("Another country already has that name.") from None
    rows = [
        KybDocumentType(
            **d.model_dump(exclude={"input_kind"}),
            country=payload.country,
            input_kind=KybInputKind(d.input_kind),
            active=True,
        )
        for d in payload.documents
    ]
    db.add_all(rows)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict(f"{payload.country} is already set up.") from None
    record_action(
        db, admin=admin, action="kyb_country.create", target_type="country", target_id=payload.country,
        details={
            "country": {k: v for k, v in fields.items() if v is not None},
            "documents": [{"code": r.code, "name": r.name, "is_mandatory": r.is_mandatory} for r in rows],
        },
    )
    await db.commit()
    for r in rows:
        await db.refresh(r)
    return [_out(r) for r in sorted(rows, key=lambda r: (r.sort_order, r.name))]


@router.post("", response_model=DocTypeAdminOut, response_model_by_alias=True, status_code=201)
async def create_type(payload: DocTypeCreate, admin: CanManageCatalog, db: DbSession) -> DocTypeAdminOut:
    """Add a document to a country that is already set up (new countries go
    through ``POST /admin/kyb/countries``)."""
    if not await _country_exists(db, payload.country):
        raise BadRequest(f"Add {payload.country} as a country first, with its required documents.")
    t = KybDocumentType(**payload.model_dump(exclude={"input_kind"}), input_kind=KybInputKind(payload.input_kind))
    db.add(t)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise Conflict(f"{payload.country} already has a document type with code '{payload.code}'.") from None
    record_action(db, admin=admin, action="kyb_type.create", target_type="kyb_document_type",
                  target_id=t.id, details=_snapshot(t) | {"country": t.country, "code": t.code})
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.patch("/{type_id}", response_model=DocTypeAdminOut, response_model_by_alias=True)
async def update_type(type_id: str, payload: DocTypeUpdate, admin: CanManageCatalog, db: DbSession) -> DocTypeAdminOut:
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
    loses_required = (before["is_mandatory"] and before["active"]) and not (t.is_mandatory and t.active)
    if loses_required and await _other_required_count(db, t) == 0:
        name, country = t.name, t.country
        await db.rollback()
        raise BadRequest(
            f"{name} is the last required document for {country}. "
            "Make another document required first — every country needs at least one."
        )
    changes = {k: {"from": before[k], "to": after[k]} for k in _EDITABLE if before[k] != after[k]}
    if changes:
        record_action(db, admin=admin, action="kyb_type.update", target_type="kyb_document_type",
                      target_id=t.id, details={"country": t.country, "code": t.code, "changes": changes})
    await db.commit()
    await db.refresh(t)
    return _out(t)
