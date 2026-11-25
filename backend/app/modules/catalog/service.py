"""Catalog rules: photo uploads, seller listings and their review status,
category templates, the public catalog, contact reveal."""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic.alias_generators import to_camel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    PayloadTooLarge,
    TooManyRequests,
    UnsupportedMediaType,
)
from app.core.time import utcnow
from app.modules.verification.rules import configured_countries
from app.integrations.storage import IMAGE_TYPES, StorageError, detect, get_storage
from app.models.business import Business
from app.models.contact_reveal import ContactReveal
from app.models.listing import (
    ALL_CATEGORIES,
    CategoryCertificateRequirement,
    CertificateType,
    ProductCertificate,
    ProductSpec,
    SpecParameter,
)
from app.models.product import ListingStatus, Product
from app.models.user import User
from app.modules.accounts.service import get_owner
from app.modules.accounts.uniqueness import commit_or_conflict
from app.modules.catalog.lifecycle import transition
from app.modules.masking import service as masking
from app.shared import leakfilter
from app.modules.catalog.queries import hydrate_businesses, public_products_stmt, visible_products_select
from app.modules.catalog.schemas import (
    LIVE_FIELDS,
    MAX_PHOTOS_PER_PRODUCT,
    CatalogFacets,
    CategoryTemplate,
    CertificateOut,
    CertificateTypeOut,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    PublicCertificate,
    PublicProductCard,
    PublicProductDetail,
    PublicProductList,
    PublicSeller,
    RevealedContact,
    SpecIn,
    SpecOut,
    SpecParameterOut,
)
from app.modules.fx import service as fx
from app.shared.images import strip_metadata

MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_PREFIX = "products"
PHOTO_URL_PREFIX = "/uploads/products/"
PHOTO_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

REVEAL_WINDOW = timedelta(hours=1)
REVEAL_MAX_PER_WINDOW = 20

S = ListingStatus

#: Request field → model column, where they differ.
_COLUMN = {"price_min": "price_per_unit"}
#: Fields whose change on a published listing waits for a reviewer.
_REVIEWED_FIELDS = (
    "name", "category", "variety", "description", "grade", "hs_code", "origin_country", "origin_state",
    "packaging", "unit", "capacity_per_month", "capacity_unit", "lead_time_days", "incoterms", "port_of_loading",
    "photos",
)
_BLANK_TO_NONE = ("variety", "description", "grade", "origin_state", "port_of_loading")


# ── Photos ───────────────────────────────────────────────────────────


def photo_key(filename: str) -> str | None:
    """Storage key for a served photo filename, or None if malformed."""
    return f"{PHOTO_PREFIX}/{filename}" if PHOTO_FILENAME_RE.match(filename) else None


async def store_photo(content: bytes) -> str:
    """Validate by magic bytes, drop the metadata, store, return the public
    relative URL."""
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_PHOTO_BYTES:
        raise PayloadTooLarge("Image must be under 5 MB")
    ftype = detect(content)
    if ftype is None or ftype not in IMAGE_TYPES:
        raise UnsupportedMediaType("Only JPG, PNG or WEBP images are supported")
    filename = f"{uuid.uuid4().hex}.{ftype.ext}"
    content = await strip_metadata(content, ftype)
    await get_storage().save(content, f"{PHOTO_PREFIX}/{filename}", ftype.mime)
    return f"{PHOTO_URL_PREFIX}{filename}"


async def read_photo(filename: str) -> bytes:
    key = photo_key(filename)
    if key is None:
        raise NotFound("Not found")
    try:
        return await get_storage().open(key)
    except StorageError:
        raise NotFound("Not found") from None


async def _validate_photos(photos: list[str]) -> list[str]:
    """De-duplicated photo URLs, each one a file this API stored. A draft may
    have none; the submit checklist asks for the first."""
    unique = list(dict.fromkeys(p.strip() for p in photos if p and p.strip()))
    if len(unique) > MAX_PHOTOS_PER_PRODUCT:
        raise BadRequest(f"At most {MAX_PHOTOS_PER_PRODUCT} photos per product")
    storage = get_storage()
    for url in unique:
        filename = url[len(PHOTO_URL_PREFIX):] if url.startswith(PHOTO_URL_PREFIX) else ""
        key = photo_key(filename)
        if key is None or not await storage.exists(key):
            raise BadRequest("Photos must be uploaded via /products/upload-photo first.")
    return unique


# ── Category templates ───────────────────────────────────────────────


def spec_parameter_out(p: SpecParameter) -> SpecParameterOut:
    return SpecParameterOut(
        id=str(p.id), category=p.category, code=p.code, name=p.name, value_type=p.value_type, unit=p.unit,
        default_operator=p.default_operator, test_method=p.test_method, is_required=p.is_required,
        sort_order=p.sort_order, active=p.active,
    )


def certificate_type_out(t: CertificateType, *, required: bool | None = None) -> CertificateTypeOut:
    """``required`` is the answer for one category (see
    :func:`required_certificate_ids`); without it, the type's own flag."""
    return CertificateTypeOut(
        id=str(t.id), category=t.category, code=t.code, name=t.name, help_text=t.help_text,
        is_required=t.is_required if required is None else required, sort_order=t.sort_order, active=t.active,
    )


async def _spec_parameters(db: AsyncSession, category: str) -> list[SpecParameter]:
    """The category's active template rows, in display order."""
    return list(
        await db.scalars(
            select(SpecParameter)
            .where(SpecParameter.category == category, SpecParameter.active.is_(True))
            .order_by(SpecParameter.sort_order, SpecParameter.name)
        )
    )


async def _certificate_types(db: AsyncSession, category: str) -> list[CertificateType]:
    """Active certificate types for the category, including the ones that
    apply to every category."""
    return list(
        await db.scalars(
            select(CertificateType)
            .where(CertificateType.category.in_((category, ALL_CATEGORIES)), CertificateType.active.is_(True))
            .order_by(CertificateType.sort_order, CertificateType.name)
        )
    )


async def required_certificate_ids(db: AsyncSession, category: str) -> set[uuid.UUID]:
    """The document types a listing in ``category`` must carry: those
    required everywhere, and those required for this category (A-049)."""
    everywhere = await db.scalars(
        select(CertificateType.id).where(
            CertificateType.category.in_((category, ALL_CATEGORIES)), CertificateType.is_required.is_(True)
        )
    )
    here = await db.scalars(
        select(CategoryCertificateRequirement.certificate_type_id).where(CategoryCertificateRequirement.category == category)
    )
    return set(everywhere) | set(here)


async def category_template(db: AsyncSession, category: str) -> CategoryTemplate:
    required = await required_certificate_ids(db, category)
    return CategoryTemplate(
        category=category,
        spec_parameters=[spec_parameter_out(p) for p in await _spec_parameters(db, category)],
        certificate_types=[
            certificate_type_out(t, required=t.id in required) for t in await _certificate_types(db, category)
        ],
    )


# ── Specifications ───────────────────────────────────────────────────


def _clean_number(raw: str, name: str) -> str:
    try:
        number = Decimal(raw.replace(",", "").strip())
    except InvalidOperation:
        raise BadRequest(f"{name} must be a number.") from None
    if not number.is_finite() or number < 0 or number >= Decimal("10000000000"):
        raise BadRequest(f"{name} must be a number.")
    return format(number.quantize(Decimal("0.0001")).normalize(), "f")


async def _clean_specs(db: AsyncSession, category: str, specs: list[SpecIn]) -> list[dict[str, Any]]:
    """Validate spec rows against the category template. Returns plain,
    JSON-safe rows (also the shape stored in ``pending_revision``)."""
    params = {str(p.id): p for p in await _spec_parameters(db, category)}
    clean: dict[str, dict[str, Any]] = {}
    for row in specs:
        param = params.get(row.parameter_id.strip().lower())
        if param is None:
            raise BadRequest("One of the specifications doesn't belong to this category. Reload the form and retry.")
        value = _clean_number(row.value, param.name) if param.value_type == "number" else row.value
        clean[str(param.id)] = {
            "parameter_id": str(param.id),
            "value": value,
            "operator": row.operator or param.default_operator,
            "test_method": row.test_method or None,
        }
    return [clean[k] for k in sorted(clean, key=lambda pid: (params[pid].sort_order, params[pid].name))]


async def _stored_specs(db: AsyncSession, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Each listing's live spec rows in the same plain shape as
    :func:`_clean_specs`, plus the parameter's display fields."""
    out: dict[uuid.UUID, list[dict[str, Any]]] = {pid: [] for pid in product_ids}
    if not product_ids:
        return out
    rows = await db.execute(
        select(ProductSpec, SpecParameter)
        .join(SpecParameter, SpecParameter.id == ProductSpec.parameter_id)
        .where(ProductSpec.product_id.in_(product_ids))
        .order_by(SpecParameter.sort_order, SpecParameter.name)
    )
    for spec, param in rows:
        value = (
            format(Decimal(spec.value_number).normalize(), "f") if spec.value_number is not None else spec.value_text
        )
        out[spec.product_id].append(
            {
                "parameter_id": str(param.id), "value": value, "operator": spec.operator,
                "test_method": spec.test_method, "code": param.code, "name": param.name, "unit": param.unit,
            }
        )
    return out


def _spec_core(rows: list[dict[str, Any]]) -> list[tuple]:
    return sorted((r["parameter_id"], r["value"], r["operator"], r.get("test_method")) for r in rows)


async def replace_specs(db: AsyncSession, product: Product, rows: list[dict[str, Any]]) -> None:
    params = {
        str(p.id): p
        for p in await db.scalars(select(SpecParameter).where(SpecParameter.id.in_([uuid.UUID(r["parameter_id"]) for r in rows])))
    } if rows else {}
    await db.execute(delete(ProductSpec).where(ProductSpec.product_id == product.id))
    for row in rows:
        param = params.get(row["parameter_id"])
        if param is None:  # retired between the edit and its approval
            continue
        numeric = param.value_type == "number"
        db.add(
            ProductSpec(
                product_id=product.id, parameter_id=param.id,
                value_number=Decimal(row["value"]) if numeric else None,
                value_text=None if numeric else row["value"],
                operator=row["operator"], test_method=row.get("test_method"),
            )
        )


async def _specs_out(db: AsyncSession, rows: list[dict[str, Any]]) -> list[SpecOut]:
    """Spec rows for a response; rows from a pending revision are joined to
    their parameter here."""
    missing = [uuid.UUID(r["parameter_id"]) for r in rows if "name" not in r]
    params = (
        {str(p.id): p for p in await db.scalars(select(SpecParameter).where(SpecParameter.id.in_(missing)))}
        if missing else {}
    )
    out = []
    for r in rows:
        p = params.get(r["parameter_id"])
        out.append(
            SpecOut(
                parameter_id=r["parameter_id"],
                code=r.get("code") or (p.code if p else ""),
                name=r.get("name") or (p.name if p else "Specification"),
                unit=r.get("unit") if "name" in r else (p.unit if p else None),
                value=r["value"], operator=r["operator"], test_method=r.get("test_method"),
            )
        )
    return out


# ── Certificates (read side; uploads live in certificates.py) ────────


def certificate_url(product_id: uuid.UUID, certificate_id: uuid.UUID) -> str:
    return f"/products/{product_id}/certificates/{certificate_id}/file"


async def stored_certificates(
    db: AsyncSession, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[ProductCertificate, CertificateType]]]:
    out: dict[uuid.UUID, list[tuple[ProductCertificate, CertificateType]]] = {pid: [] for pid in product_ids}
    if not product_ids:
        return out
    rows = await db.execute(
        select(ProductCertificate, CertificateType)
        .join(CertificateType, CertificateType.id == ProductCertificate.certificate_type_id)
        .where(ProductCertificate.product_id.in_(product_ids))
        .order_by(CertificateType.sort_order, CertificateType.name)
    )
    for cert, ctype in rows:
        out[cert.product_id].append((cert, ctype))
    return out


def certificate_out(cert: ProductCertificate, ctype: CertificateType, *, url: str | None = None) -> CertificateOut:
    return CertificateOut(
        id=str(cert.id), certificate_type_id=str(ctype.id), code=ctype.code, name=ctype.name,
        filename=cert.original_filename, mime_type=cert.mime_type, size_bytes=cert.size_bytes,
        visibility=cert.visibility, uploaded_at=cert.created_at,
        url=url or certificate_url(cert.product_id, cert.id),
    )


# ── Submit checklist ─────────────────────────────────────────────────

#: Decision A-023, the plan's candidate minimum (3.7). (field, what to ask for)
_REQUIRED_TO_SUBMIT = (
    ("description", "a description"),
    ("grade", "the grade or quality"),
    ("origin_country", "the country of origin"),
    ("origin_state", "the state or region of origin"),
    ("moq", "the minimum order quantity"),
    ("capacity_per_month", "the monthly capacity"),
    ("lead_time_days", "the lead time"),
    ("price_min", "the minimum price"),
    ("price_max", "the maximum price"),
    ("price_valid_until", "the price validity date"),
)


def _listing_values(product: Product) -> dict[str, Any]:
    """The listing's live values under their request field names."""
    values = {f: getattr(product, _COLUMN.get(f, f)) for f in (*_REVIEWED_FIELDS, *LIVE_FIELDS)}
    values["incoterms"] = list(product.incoterms or [])
    values["photos"] = list(product.photos or [])
    return values


async def missing_to_submit(
    db: AsyncSession, values: dict[str, Any], specs: list[dict[str, Any]], certificate_type_ids: set[uuid.UUID],
    *, today: date,
) -> list[str]:
    """What the listing still needs, in the seller's words. Empty = ready."""
    missing = [label for field, label in _REQUIRED_TO_SUBMIT if values.get(field) in (None, "")]
    valid_until = values.get("price_valid_until")
    if valid_until is not None and valid_until < today:
        missing.append("a price validity date that hasn't passed")
    if not values.get("incoterms"):
        missing.append("at least one incoterm")
    if not values.get("photos"):
        missing.append("at least one photo")
    filled = {r["parameter_id"] for r in specs}
    missing += [
        f"the specification “{p.name}”"
        for p in await _spec_parameters(db, values["category"])
        if p.is_required and str(p.id) not in filled
    ]
    required = await required_certificate_ids(db, values["category"])
    missing += [
        f"the document “{t.name}”"
        for t in await _certificate_types(db, values["category"])
        if t.id in required and t.id not in certificate_type_ids
    ]
    return missing


# ── Seller listings ──────────────────────────────────────────────────


async def _own_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    """The listing, fetched with its owner in the query: a stranger gets 404."""
    product = (
        await db.scalar(
            select(Product).where(
                Product.id == product_id, Product.business_id == user.business_id, Product.deleted_at.is_(None)
            )
        )
        if product_id
        else None
    )
    if product is None:
        raise NotFound("Product not found")
    return product


def _revision_out(revision: dict[str, Any] | None, specs: list[SpecOut] | None) -> dict[str, Any] | None:
    if not revision:
        return None
    out = {to_camel(k): v for k, v in revision.items() if k != "specs"}
    if specs is not None:
        out["specs"] = [s.model_dump(by_alias=True) for s in specs]
    return out


async def read_products(db: AsyncSession, products: list[Product]) -> list[ProductRead]:
    """Listings with their specs, certificates and submit checklist."""
    ids = [p.id for p in products]
    specs = await _stored_specs(db, ids)
    certs = await stored_certificates(db, ids)
    today = utcnow().date()
    out = []
    for p in products:
        revision = p.pending_revision or None
        revision_specs = await _specs_out(db, revision["specs"]) if revision and "specs" in revision else None
        needs_checklist = p.status in (S.draft, S.rejected)
        missing = (
            await missing_to_submit(
                db, _listing_values(p), specs[p.id], {c.certificate_type_id for c, _ in certs[p.id]}, today=today
            )
            if needs_checklist
            else []
        )
        out.append(
            ProductRead(
                id=str(p.id), name=p.name, category=p.category, variety=p.variety, description=p.description,
                grade=p.grade, hs_code=p.hs_code, origin_country=p.origin_country, origin_state=p.origin_state,
                packaging=p.packaging, quantity=p.quantity, unit=p.unit, moq=p.moq,
                capacity_per_month=p.capacity_per_month, capacity_unit=p.capacity_unit,
                lead_time_days=p.lead_time_days, price_min=p.price_per_unit, price_max=p.price_max,
                currency=p.currency, price_usd=p.price_usd, price_usd_max=p.price_usd_max,
                price_usd_as_of=p.price_usd_as_of, price_valid_until=p.price_valid_until,
                incoterms=list(p.incoterms or []), port_of_loading=p.port_of_loading, photos=list(p.photos or []),
                specs=await _specs_out(db, specs[p.id]),
                certificates=[certificate_out(c, t) for c, t in certs[p.id]],
                status=p.status, submitted_at=p.submitted_at, published_at=p.published_at,
                rejection_reason=p.rejection_reason,
                pending_revision=_revision_out(revision, revision_specs),
                has_pending_revision=bool(revision),
                revision_submitted_at=p.revision_submitted_at,
                revision_rejection_reason=p.revision_rejection_reason,
                missing=missing, created_at=p.created_at, updated_at=p.updated_at,
            )
        )
    return out


async def read_product(db: AsyncSession, product: Product) -> ProductRead:
    return (await read_products(db, [product]))[0]


async def list_own_products(db: AsyncSession, user: User) -> list[Product]:
    """The business's listings (not deleted), newest first."""
    return list(
        await db.scalars(
            select(Product)
            .where(Product.business_id == user.business_id, Product.deleted_at.is_(None))
            .order_by(Product.created_at.desc())
        )
    )


async def get_own_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    return await _own_product(db, user, product_id)


async def _normalise(db: AsyncSession, changes: dict[str, Any]) -> dict[str, Any]:
    """Clean a payload's values (photos exist, currency supported, origin
    onboarded, validity date not past, blanks → null)."""
    for field in _BLANK_TO_NONE:
        if field in changes and not changes[field]:
            changes[field] = None
    if changes.get("origin_country"):
        # The same list the listing form offers: the countries Corridor onboards.
        onboarded = await configured_countries(db)
        if changes["origin_country"] not in onboarded:
            raise BadRequest(f"Choose a country of origin we trade: {', '.join(onboarded)}.")
    if changes.get("price_valid_until") is not None and changes["price_valid_until"] < utcnow().date():
        raise BadRequest("The price validity date has passed. Choose today or a later date.")
    if "currency" in changes:
        changes["currency"] = fx.ensure_supported(changes["currency"])
    if "photos" in changes:
        changes["photos"] = await _validate_photos(changes["photos"] or [])
    if "incoterms" in changes:
        changes["incoterms"] = list(dict.fromkeys(changes["incoterms"] or []))
    return changes


async def _set_fields(db: AsyncSession, product: Product, values: dict[str, Any]) -> None:
    """Write fields to the listing and keep the USD mirror of the price in step."""
    for field, value in values.items():
        setattr(product, _COLUMN.get(field, field), value)
    if product.price_max is not None and product.price_per_unit is None:
        raise BadRequest("Enter the minimum price as well as the maximum.")
    if (
        product.price_max is not None
        and product.price_per_unit is not None
        and product.price_max < product.price_per_unit
    ):
        raise BadRequest("The maximum price can't be lower than the minimum price.")
    if product.moq is not None and product.quantity is not None and product.moq > product.quantity:
        raise BadRequest("MOQ can't be larger than the available quantity.")
    if LIVE_FIELDS & values.keys():
        rates = await fx.get_latest_rates(db)
        product.price_usd, product.price_usd_as_of = fx.price_usd_for(product.price_per_unit, product.currency, rates)
        product.price_usd_max, _ = fx.price_usd_for(product.price_max, product.currency, rates)


async def create_product(db: AsyncSession, user: User, payload: ProductCreate) -> Product:
    """A new listing starts as a draft. Any signed-in user may draft for their
    business; it reaches the market only after :func:`submit_product` and a
    reviewer's approval."""
    changes = await _normalise(db, payload.model_dump(exclude_unset=True, exclude={"specs"}))
    await _refuse_leaks(db, user.business_id, changes)
    product = Product(
        business_id=user.business_id, created_by_user_id=user.id, name=payload.name, category=payload.category,
        unit=payload.unit or "MT", currency=changes.get("currency") or "INR", status=S.draft, photos=[], incoterms=[],
    )
    await _set_fields(db, product, {k: v for k, v in changes.items() if v is not None})
    db.add(product)
    await db.flush()
    if payload.specs:
        await replace_specs(db, product, await _clean_specs(db, product.category, payload.specs))
    await commit_or_conflict(db)
    await db.refresh(product)
    return product


#: Listing text a buyer reads, with the label used in the refusal.
LEAK_CHECKED_FIELDS = {
    "name": "product name",
    "variety": "variety",
    "grade": "grade",
    "description": "description",
    "port_of_loading": "port of loading",
}


async def _refuse_leaks(db: AsyncSession, business_id: uuid.UUID, changes: dict[str, Any]) -> None:
    """Listing text must not carry a way to reach the seller directly, or
    the seller's own name (plan 18.5). Text that only looks doubtful is saved
    for the reviewer."""
    texts = {f: changes.get(f) for f in LEAK_CHECKED_FIELDS if isinstance(changes.get(f), str)}
    if not texts:
        return
    found = leakfilter.check_all(texts, await masking.legal_name_for_text_check(db, business_id))
    for field, result in found.items():
        if result.blocked:
            raise BadRequest(
                f"Remove the {_join(list(result.reasons))} from the {LEAK_CHECKED_FIELDS[field]}. "
                "Buyers reach you through Corridor One X."
            )


def _json_safe(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def _from_revision(field: str, value: Any) -> Any:
    return Decimal(value) if field in _DECIMAL_REVISION_FIELDS and value is not None else value


#: Price fields that go to the reviewer together when the price swings.
_PRICE_FIELDS = frozenset({"price_min", "price_max", "currency"})
_DECIMAL_REVISION_FIELDS = frozenset({"capacity_per_month", "price_min", "price_max"})
#: How far the price of a live listing may move without a review (20%).
PRICE_REVIEW_SWING = Decimal("0.20")


def _price_swings(product: Product, live: dict[str, Any]) -> bool:
    """Whether this edit moves a live listing's price by more than
    :data:`PRICE_REVIEW_SWING` from the approved one, or changes its currency."""
    if "currency" in live and live["currency"] != product.currency:
        return True
    for field, column in (("price_min", "price_per_unit"), ("price_max", "price_max")):
        old, new = getattr(product, column), live.get(field)
        if field not in live or old is None or new is None or old == 0:
            continue
        if abs(Decimal(new) - old) / old > PRICE_REVIEW_SWING:
            return True
    return False


async def apply_revision(db: AsyncSession, product: Product, fields: dict[str, Any]) -> None:
    """Write an approved revision to the listing (request names, as stored in
    ``pending_revision``), keeping the USD price mirror in step."""
    await _set_fields(db, product, {f: _from_revision(f, v) for f, v in fields.items()})


async def update_product(db: AsyncSession, user: User, product_id: uuid.UUID | None, payload: ProductUpdate) -> Product:
    """Edit a listing. A draft or rejected listing changes directly. On a
    published or paused one, price and stock fields change at once and
    everything else is held in ``pending_revision`` for a reviewer while the
    published version stays live."""
    product = await _own_product(db, user, product_id)
    if product.status == S.under_review:
        raise Conflict("This listing is with the reviewer. Withdraw it to make changes.")
    sent = payload.model_fields_set
    changes = await _normalise(db, payload.model_dump(include=sent - {"specs"}))
    await _refuse_leaks(db, user.business_id, changes)
    for field in ("name", "category", "unit", "currency"):
        if field in changes and changes[field] is None:
            raise BadRequest("Name, category, unit and currency can't be empty.")
    specs_sent = "specs" in sent

    if product.status in (S.draft, S.rejected):
        category_changed = "category" in changes and changes["category"] != product.category
        await _set_fields(db, product, changes)
        if specs_sent:
            await replace_specs(db, product, await _clean_specs(db, product.category, payload.specs or []))
        elif category_changed:
            # The old category's rows mean nothing under the new template.
            await replace_specs(db, product, [])
        await commit_or_conflict(db)
        await db.refresh(product)
        return product

    live = {f: v for f, v in changes.items() if f in LIVE_FIELDS}
    # A big price move (or a new currency) goes to the reviewer with the rest
    # of the price, so a seller can't swing it to bait buyers or game ranking.
    reviewed_price = _PRICE_FIELDS & live.keys() if _price_swings(product, live) else set()
    await _set_fields(db, product, {f: v for f, v in live.items() if f not in reviewed_price})

    current = _listing_values(product)
    revision = dict(product.pending_revision or {})
    for field in (*_REVIEWED_FIELDS, *sorted(reviewed_price)):
        if field not in changes:
            continue
        if changes[field] == current[field]:
            revision.pop(field, None)  # set back to the published value
        else:
            revision[field] = _json_safe(changes[field])
    live_specs = (await _stored_specs(db, [product.id]))[product.id]
    category = revision.get("category", product.category)
    if specs_sent:
        proposed = await _clean_specs(db, category, payload.specs or [])
        if _spec_core(proposed) == _spec_core(live_specs):
            revision.pop("specs", None)
        else:
            revision["specs"] = proposed
    elif "category" in revision and "specs" not in revision:
        revision["specs"] = []

    if revision:
        candidate = {**current, **{f: _from_revision(f, v) for f, v in revision.items() if f != "specs"}}
        certs = (await stored_certificates(db, [product.id]))[product.id]
        missing = await missing_to_submit(
            db, candidate, revision.get("specs", live_specs), {c.certificate_type_id for c, _ in certs},
            today=utcnow().date(),
        )
        if missing:
            raise BadRequest("Before these changes can be reviewed, add " + _join(missing) + ".")
        product.pending_revision = revision
        product.revision_submitted_at = utcnow()
        product.revision_rejection_reason = None
    else:
        product.pending_revision = None
        product.revision_submitted_at = None
    await commit_or_conflict(db)
    await db.refresh(product)
    return product


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


async def submit_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    """Send a draft (or a rejected listing the seller fixed) to the review
    queue. The business must be verified and the listing complete."""
    product = await _own_product(db, user, product_id)
    if not user.business.is_verified:
        raise Forbidden("Get your business verified before submitting a listing for review.")
    if product.status not in (S.draft, S.rejected):
        transition(product, S.under_review, now=utcnow())  # raises the right Conflict
    specs = (await _stored_specs(db, [product.id]))[product.id]
    certs = (await stored_certificates(db, [product.id]))[product.id]
    missing = await missing_to_submit(
        db, _listing_values(product), specs, {c.certificate_type_id for c, _ in certs}, today=utcnow().date()
    )
    if missing:
        raise BadRequest("Before submitting, add " + _join(missing) + ".")
    transition(product, S.under_review, now=utcnow())
    await db.commit()
    await db.refresh(product)
    return product


async def _move(db: AsyncSession, user: User, product_id: uuid.UUID | None, to: str) -> Product:
    product = await _own_product(db, user, product_id)
    transition(product, to, now=utcnow())
    await db.commit()
    await db.refresh(product)
    return product


async def withdraw_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    """Take a listing back from the review queue to edit it."""
    product = await _own_product(db, user, product_id)
    if product.status != S.under_review:
        raise Conflict("Only a listing that is with the reviewer can be withdrawn.")
    return await _move(db, user, product_id, S.draft)


async def pause_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    """Hide a published listing from the market without losing its approval."""
    product = await _own_product(db, user, product_id)
    if product.status != S.published:
        raise Conflict("Only a published listing can be paused.")
    return await _move(db, user, product_id, S.paused)


async def resume_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    product = await _own_product(db, user, product_id)
    if product.status != S.paused:
        raise Conflict("Only a paused listing can be resumed.")
    return await _move(db, user, product_id, S.published)


async def discard_revision(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> Product:
    """Drop the edits waiting for review; the published version is untouched."""
    product = await _own_product(db, user, product_id)
    product.pending_revision = None
    product.revision_submitted_at = None
    product.revision_rejection_reason = None
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> None:
    """Soft delete (the listing leaves the market; reveals keep their history)."""
    product = await _own_product(db, user, product_id)
    product.deleted_at = utcnow()
    await db.commit()


# ── Public catalog ───────────────────────────────────────────────────


def can_see_prices(viewer: User | None, seller_business_id: uuid.UUID | None = None) -> bool:
    """Decision A-022: the price range is for signed-in, verified businesses.
    A seller always sees their own."""
    if viewer is None:
        return False
    return viewer.business.is_verified or viewer.business_id == seller_business_id


def _seller_dto(business: Business | None, business_id: uuid.UUID) -> PublicSeller:
    return PublicSeller(
        company_code=business.company_code if business else None,
        state=business.state if business else None,
    )


def _card_kwargs(p: Product, business: Business | None, viewer: User | None) -> dict:
    priced = can_see_prices(viewer, p.business_id)
    return dict(
        id=str(p.id),
        name=p.name,
        category=p.category,
        variety=p.variety,
        grade=p.grade,
        origin_country=p.origin_country,
        origin_state=p.origin_state,
        packaging=p.packaging,
        quantity=p.quantity,
        unit=p.unit,
        moq=p.moq,
        capacity_per_month=p.capacity_per_month,
        capacity_unit=p.capacity_unit,
        incoterms=list(p.incoterms or []),
        price_visible=priced,
        price_min=p.price_per_unit if priced else None,
        price_max=p.price_max if priced else None,
        currency=p.currency if priced else None,
        price_usd=p.price_usd if priced else None,
        price_usd_max=p.price_usd_max if priced else None,
        price_usd_as_of=p.price_usd_as_of if priced else None,
        price_valid_until=p.price_valid_until if priced else None,
        photo=(p.photos or [None])[0],
        seller=_seller_dto(business, p.business_id),
    )


async def public_list(
    db: AsyncSession,
    *,
    viewer: User | None,
    category: str | None,
    variety: str | None,
    origin_state: str | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
    order_quantity: Decimal | None,
    q: str | None,
    limit: int,
    offset: int,
    price_currency: str | None = None,
) -> PublicProductList:
    """Price bounds are typed in ``price_currency`` (default USD), converted
    to USD with the latest rates and matched against each listing's range.
    They are ignored for a viewer who may not see prices: otherwise a guest
    could find any listing's price by narrowing the filter."""
    min_usd = max_usd = None
    if viewer is not None and viewer.business.is_verified:
        min_usd, max_usd = await fx.usd_bounds(db, min_price, max_price, price_currency)
    base = public_products_stmt(
        category=category,
        variety=variety,
        origin_state=origin_state,
        min_price_usd=min_usd,
        max_price_usd=max_usd,
        order_quantity=order_quantity,
        q=q,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(await db.scalars(base.order_by(Product.created_at.desc()).offset(offset).limit(limit)))
    sellers = await hydrate_businesses(db, [r.business_id for r in rows])
    items = [PublicProductCard(**_card_kwargs(r, sellers.get(r.business_id), viewer)) for r in rows]
    return PublicProductList(total=total, items=items)


async def _visible_product(db: AsyncSession, product_id: uuid.UUID | None) -> Product:
    if product_id is None:
        raise NotFound("Product not found")
    product = await db.scalar(visible_products_select().where(Product.id == product_id))
    if product is None:
        raise NotFound("Product not found")
    return product


async def public_detail(db: AsyncSession, product_id: uuid.UUID | None, viewer: User | None) -> PublicProductDetail:
    p = await _visible_product(db, product_id)
    business = await db.get(Business, p.business_id)
    specs = (await _stored_specs(db, [p.id]))[p.id]
    certs = (await stored_certificates(db, [p.id]))[p.id]
    return PublicProductDetail(
        **_card_kwargs(p, business, viewer),
        description=p.description,
        photos=list(p.photos or []),
        specs=await _specs_out(db, specs),
        certificates=[
            PublicCertificate(id=str(c.id), name=t.name, url=certificate_url(p.id, c.id))
            for c, t in certs
            if c.visibility == "downloadable"
        ],
    )


async def facets(db: AsyncSession, viewer: User | None) -> CatalogFacets:
    visible = visible_products_select().subquery()
    cats = (
        await db.execute(
            select(visible.c.category, func.count())
            .group_by(visible.c.category)
            .order_by(func.count().desc())
        )
    ).all()
    states = (
        await db.execute(
            select(visible.c.origin_state, func.count())
            .where(visible.c.origin_state.is_not(None))
            .group_by(visible.c.origin_state)
            .order_by(func.count().desc())
        )
    ).all()
    price_min = price_max = None
    if viewer is not None and viewer.business.is_verified:
        price_min, price_max = (
            await db.execute(
                select(func.min(visible.c.price_usd), func.max(func.coalesce(visible.c.price_usd_max, visible.c.price_usd)))
            )
        ).one()
    rates = await fx.get_latest_rates(db)
    return CatalogFacets(
        categories=[{"value": c, "count": n} for c, n in cats],
        origin_states=[{"value": s, "count": n} for s, n in states],
        price_min=price_min,
        price_max=price_max,
        price_currency=fx.BASE,
        fx_as_of=rates.as_of,
    )


# ── Contact reveal ───────────────────────────────────────────────────


async def _check_reveal_budget(db: AsyncSession, buyer_business_id: uuid.UUID) -> None:
    """DB-backed (survives restarts, shared across workers): at most
    REVEAL_MAX_PER_WINDOW *new* reveals per buyer BUSINESS per hour."""
    since = utcnow() - REVEAL_WINDOW
    recent = await db.scalar(
        select(func.count(ContactReveal.id)).where(
            ContactReveal.buyer_business_id == buyer_business_id, ContactReveal.revealed_at >= since
        )
    ) or 0
    if recent >= REVEAL_MAX_PER_WINDOW:
        raise TooManyRequests(
            f"Your business hit the reveal limit ({REVEAL_MAX_PER_WINDOW}/hour). Come back shortly.",
            retry_after=int(REVEAL_WINDOW.total_seconds()),
        )


async def reveal_contact(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> RevealedContact:
    """Business-to-business. Gates: signed in (router), buyer business
    verified, product visible (seller business verified), not own
    business, per-business hourly budget. Idempotent per (buyer business,
    product)."""
    if not settings.contact_reveal_enabled:
        raise NotFound("Contact reveal is no longer available. Corridor One X now handles the trade for both sides.")
    buyer = user.business
    if not buyer.is_verified:
        raise Forbidden("Get your business verified before revealing seller contact details.")
    product = await _visible_product(db, product_id)
    # Plain values: a rollback below expires ORM instances.
    seller_id, pid, buyer_id, user_id = product.business_id, product.id, buyer.id, user.id
    if seller_id == buyer_id:
        raise BadRequest("This is your own business's listing — nothing to reveal.")

    def _existing_stmt():
        return select(ContactReveal).where(
            ContactReveal.buyer_business_id == buyer_id, ContactReveal.product_id == pid
        )

    existing = await db.scalar(_existing_stmt())
    if existing is None:
        await _check_reveal_budget(db, buyer_id)
        revealed_at = utcnow()
        db.add(
            ContactReveal(
                buyer_business_id=buyer_id,
                revealed_by_user_id=user_id,
                seller_business_id=seller_id,
                product_id=pid,
                revealed_at=revealed_at,
            )
        )
        try:
            await db.commit()
        except IntegrityError:  # double-click race on UNIQUE(buyer business, product)
            await db.rollback()
            existing = await db.scalar(_existing_stmt())
            if existing is None:
                raise
            revealed_at = existing.revealed_at
    else:
        revealed_at = existing.revealed_at

    seller = await db.get(Business, seller_id)
    owner = await get_owner(db, seller_id)
    assert seller is not None  # guarded by visible_products_clause
    identity = await masking.identity_for_contact_reveal(db, seller_id)
    person = await masking.person_for_contact_reveal(db, owner.id if owner else None)
    return RevealedContact(
        seller_id=str(seller.id),
        full_name=person.full_name if person else None,
        business_name=identity.legal_name,
        entity_type=seller.entity_type,
        email=person.email if person else None,
        address_line=identity.address_line,
        state=seller.state,
        country=seller.country,
        website_url=identity.website_url,
        revealed_at=revealed_at,
    )
