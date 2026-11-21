"""/admin/kyb/countries/{code}/rules and /links, and
/admin/listing-templates/category-requirements: the per-country and
per-category settings that keep country-specific rules out of the code.

* Rules (A-047): characters x–y of one document's number must equal
  another's. India ships with GSTIN 3–12 = PAN.
* Links (A-052): which document keys the free-RFQ quota, and which document
  several businesses may share and is shown to the reviewer as "related".
* Category requirements (A-049): the documents a listing in a category
  must carry.

Every change is written to ``admin_actions``."""
from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import delete, select

from app.core.errors import BadRequest, NotFound
from app.core.security import parse_uuid
from app.models.country import Country, CountryDocumentRule
from app.models.kyb_document_type import KybDocumentType
from app.models.listing import ALL_CATEGORIES, CategoryCertificateRequirement, CertificateType
from app.modules.admin.deps import CanManageCatalog, CanViewCatalog
from app.modules.admin.service import record_action
from app.modules.auth.deps import DbSession
from app.modules.catalog.schemas import Category
from app.shared.schemas import CamelModel, ItemList, RequestModel, item_list

router = APIRouter()


class RuleIn(RequestModel):
    source_type_id: str
    source_start: int = Field(ge=1, le=100)
    source_end: int = Field(ge=1, le=100)
    target_type_id: str


class RulePatch(RequestModel):
    active: bool


class RuleOut(CamelModel):
    id: str
    country: str
    kind: str
    source_type_id: str
    source_name: str
    source_start: int
    source_end: int
    target_type_id: str
    target_name: str
    active: bool


class LinksIn(RequestModel):
    #: The document whose number keys the free-RFQ quota; null clears it.
    quota_document_type_id: str | None = None
    #: The document several businesses may share, flagged as "related"; null clears it.
    group_document_type_id: str | None = None


class LinksOut(CamelModel):
    country: str
    quota_document_type_id: str | None
    group_document_type_id: str | None


class RequirementsIn(RequestModel):
    certificate_type_ids: list[str] = Field(max_length=20)


class RequirementsOut(CamelModel):
    category: str
    certificate_type_ids: list[str]


async def _country(db, code: str) -> Country:
    country = await db.get(Country, code.strip().upper()[:2])
    if country is None:
        raise NotFound("Country not found")
    return country


async def _doc_type(db, country: str, type_id: str | None) -> KybDocumentType:
    row = await db.get(KybDocumentType, parse_uuid(type_id)) if type_id else None
    if row is None or row.country != country:
        raise BadRequest("Choose a document of this country.")
    return row


async def _rule_out(db, rule: CountryDocumentRule) -> RuleOut:
    source = await db.get(KybDocumentType, rule.source_type_id)
    target = await db.get(KybDocumentType, rule.target_type_id)
    return RuleOut(
        id=str(rule.id), country=rule.country, kind=rule.kind, source_type_id=str(rule.source_type_id),
        source_name=source.name if source else "", source_start=rule.source_start, source_end=rule.source_end,
        target_type_id=str(rule.target_type_id), target_name=target.name if target else "", active=rule.active,
    )


@router.get("/kyb/countries/{code}/rules", response_model=ItemList[RuleOut], response_model_by_alias=True)
async def list_rules(code: str, _: CanViewCatalog, db: DbSession) -> ItemList[RuleOut]:
    country = await _country(db, code)
    rows = await db.scalars(
        select(CountryDocumentRule).where(CountryDocumentRule.country == country.code).order_by(CountryDocumentRule.created_at)
    )
    return item_list([await _rule_out(db, r) for r in rows])


@router.post("/kyb/countries/{code}/rules", response_model=RuleOut, response_model_by_alias=True, status_code=201)
async def create_rule(code: str, payload: RuleIn, admin: CanManageCatalog, db: DbSession) -> RuleOut:
    """Characters ``sourceStart``–``sourceEnd`` (1-based, inclusive) of the
    source document's number must equal the target document's number."""
    country = await _country(db, code)
    source = await _doc_type(db, country.code, payload.source_type_id)
    target = await _doc_type(db, country.code, payload.target_type_id)
    if source.id == target.id:
        raise BadRequest("Compare two different documents.")
    if payload.source_end < payload.source_start:
        raise BadRequest("The last character can't come before the first.")
    rule = CountryDocumentRule(
        id=uuid.uuid4(), country=country.code, kind="slice_equals", source_type_id=source.id,
        source_start=payload.source_start, source_end=payload.source_end, target_type_id=target.id, active=True,
    )
    db.add(rule)
    record_action(
        db, admin=admin, action="kyb_rule.create", target_type="country", target_id=country.code,
        details={"source": source.code, "start": payload.source_start, "end": payload.source_end, "target": target.code},
    )
    await db.commit()
    await db.refresh(rule)
    return await _rule_out(db, rule)


@router.patch("/kyb/countries/{code}/rules/{rule_id}", response_model=RuleOut, response_model_by_alias=True)
async def update_rule(code: str, rule_id: str, payload: RulePatch, admin: CanManageCatalog, db: DbSession) -> RuleOut:
    """Turn a rule off or on. Rules are not deleted, so the audit trail reads."""
    country = await _country(db, code)
    rule = await db.get(CountryDocumentRule, parse_uuid(rule_id)) if parse_uuid(rule_id) else None
    if rule is None or rule.country != country.code:
        raise NotFound("Rule not found")
    rule.active = payload.active
    record_action(
        db, admin=admin, action="kyb_rule.update", target_type="country", target_id=country.code,
        details={"rule": str(rule.id), "active": payload.active},
    )
    await db.commit()
    await db.refresh(rule)
    return await _rule_out(db, rule)


@router.get("/kyb/countries/{code}/links", response_model=LinksOut, response_model_by_alias=True)
async def get_links(code: str, _: CanViewCatalog, db: DbSession) -> LinksOut:
    c = await _country(db, code)
    return LinksOut(
        country=c.code,
        quota_document_type_id=str(c.quota_document_type_id) if c.quota_document_type_id else None,
        group_document_type_id=str(c.group_document_type_id) if c.group_document_type_id else None,
    )


@router.put("/kyb/countries/{code}/links", response_model=LinksOut, response_model_by_alias=True)
async def set_links(code: str, payload: LinksIn, admin: CanManageCatalog, db: DbSession) -> LinksOut:
    """Both fields are set as sent: a null clears one."""
    c = await _country(db, code)
    quota = await _doc_type(db, c.code, payload.quota_document_type_id) if payload.quota_document_type_id else None
    group = await _doc_type(db, c.code, payload.group_document_type_id) if payload.group_document_type_id else None
    c.quota_document_type_id = quota.id if quota else None
    c.group_document_type_id = group.id if group else None
    c.updated_by = admin.email
    record_action(
        db, admin=admin, action="kyb_country.links", target_type="country", target_id=c.code,
        details={"quota": quota.code if quota else None, "group": group.code if group else None},
    )
    await db.commit()
    return await get_links(c.code, admin, db)


@router.get(
    "/listing-templates/category-requirements/{category}", response_model=RequirementsOut, response_model_by_alias=True
)
async def get_requirements(category: Category, _: CanViewCatalog, db: DbSession) -> RequirementsOut:
    ids = await db.scalars(
        select(CategoryCertificateRequirement.certificate_type_id).where(CategoryCertificateRequirement.category == category)
    )
    return RequirementsOut(category=category, certificate_type_ids=sorted(str(i) for i in ids))


@router.put(
    "/listing-templates/category-requirements/{category}", response_model=RequirementsOut, response_model_by_alias=True
)
async def set_requirements(
    category: Category, payload: RequirementsIn, admin: CanManageCatalog, db: DbSession
) -> RequirementsOut:
    """The full list of documents a listing in this category must carry.
    Listings already in the market keep going; the list applies the next
    time one is submitted or edited."""
    wanted = {parse_uuid(i) for i in payload.certificate_type_ids}
    if None in wanted:
        raise BadRequest("One of the documents isn't recognised. Reload and retry.")
    if wanted:
        found = set(await db.scalars(
            select(CertificateType.id).where(
                CertificateType.id.in_(wanted), CertificateType.category.in_((category, ALL_CATEGORIES))
            )
        ))
        if found != wanted:
            raise BadRequest("One of the documents isn't available for this category.")
    await db.execute(delete(CategoryCertificateRequirement).where(CategoryCertificateRequirement.category == category))
    for type_id in wanted:
        db.add(CategoryCertificateRequirement(category=category, certificate_type_id=type_id))
    record_action(
        db, admin=admin, action="listing_template.requirements", target_type="category", target_id=category,
        details={"certificate_type_ids": sorted(str(i) for i in wanted)},
    )
    await db.commit()
    return await get_requirements(category, admin, db)
