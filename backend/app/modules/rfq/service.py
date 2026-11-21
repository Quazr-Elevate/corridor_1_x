"""RFQ rules (build plan 05, 20).

* A draft belongs to no deal and costs nothing. Submitting it needs a
  verified business, takes a free RFQ or the RFQ_POST credits, opens the
  deal and proposes sellers by the hard rules — one transaction.
* An RFQ touching a held country stops for the desk before it is worked.
* Nothing reaches a seller until a desk user confirms the matches.
* A seller pays RFQ_VIEW the first time they open a matched RFQ, and never
  sees the buyer's name or target price.
* The desk works from company codes. A rejected or unmatched RFQ is refunded
  and its deal cancelled (decision A-038).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.business import Business
from app.models.deal import Deal
from app.models.deal import DealStatus as D
from app.models.listing import ALL_CATEGORIES, CertificateType, SpecParameter
from app.models.product import Product
from app.models.rfq import HeldCountry, Rfq, RfqMatch, TradeSetting
from app.models.rfq import RfqStatus as R
from app.models.user import User
from app.modules.catalog import service as catalog
from app.modules.catalog.queries import visible_products_select
from app.modules.credits import service as credits
from app.modules.deals import machine
from app.modules.deals.machine import Actor
from app.modules.masking import service as masking
from app.modules.rfq import matching, seed
from app.modules.rfq.schemas import (
    CertificateNeed,
    DeskLeakFlag,
    DeskRfqDetail,
    DeskRfqRow,
    MatchedRfqRow,
    MatchOut,
    MatchReason,
    RfqCreate,
    RfqRead,
    RfqSellerView,
    RfqUpdate,
    SpecLimitOut,
    SubmitCost,
)
from app.shared import leakfilter

#: RFQ text a seller reads, with the label used in a refusal.
LEAK_CHECKED = {
    "product_name": "product name", "variety": "variety", "grade": "grade", "notes": "notes",
    "destination_port": "destination port", "packaging": "packaging",
}
_BLANK_TO_NONE = ("variety", "grade", "packaging", "destination_port", "notes")
#: The most sellers one RFQ is proposed to.
MAX_PROPOSALS = 10

#: Allowed moves of an RFQ's own status.
_MOVES: dict[str, frozenset[str]] = {
    R.draft: frozenset({R.submitted, R.held}),
    R.submitted: frozenset({R.held, R.matched, R.rejected, R.unmatched, R.expired}),
    R.held: frozenset({R.submitted, R.rejected, R.expired}),
    R.matched: frozenset({R.expired}),
}
_LABEL = {
    R.draft: "a draft", R.submitted: "with the desk", R.held: "on hold", R.matched: "with sellers",
    R.rejected: "rejected", R.unmatched: "closed without a match", R.expired: "expired",
}


def spend_key(rfq_id: uuid.UUID) -> str:
    return f"rfq_post:{rfq_id}"


def view_key(match_id: uuid.UUID) -> str:
    return f"rfq_view:{match_id}"


def _move(rfq: Rfq, to: str) -> None:
    """The one place an RFQ changes status."""
    if to not in _MOVES.get(rfq.status, frozenset()):
        raise Conflict(f"This request is {_LABEL.get(rfq.status, rfq.status)}, so that isn't possible right now.")
    rfq.status = to


async def setting(db: AsyncSession, key: str) -> Decimal:
    value = await db.scalar(select(TradeSetting.value).where(TradeSetting.key == key))
    if value is None:
        raise RuntimeError(f"trade_settings has no {key!r}; run the migrations.")
    return Decimal(value)


# ── Template lookups ─────────────────────────────────────────────────


async def _parameters(db: AsyncSession, category: str) -> dict[str, SpecParameter]:
    rows = await db.scalars(select(SpecParameter).where(SpecParameter.category == category))
    return {str(p.id): p for p in rows}


async def _certificate_types(db: AsyncSession, category: str) -> dict[str, CertificateType]:
    rows = await db.scalars(
        select(CertificateType).where(CertificateType.category.in_((category, ALL_CATEGORIES)))
    )
    return {str(t.id): t for t in rows}


async def _clean_specs(db: AsyncSession, category: str, specs: list) -> list[dict[str, str]]:
    """Check the buyer's limits against the category template. Stored in
    display order as plain rows."""
    params = await _parameters(db, category)
    clean: dict[str, dict[str, str]] = {}
    for row in specs:
        param = params.get(row.parameter_id.strip().lower())
        if param is None or not param.active:
            raise BadRequest("One of the specifications doesn't belong to this category. Reload the form and retry.")
        value = catalog._clean_number(row.value, param.name) if param.value_type == "number" else row.value
        clean[str(param.id)] = {
            "parameter_id": str(param.id), "value": value, "operator": row.operator or param.default_operator,
        }
    return [clean[k] for k in sorted(clean, key=lambda pid: (params[pid].sort_order, params[pid].name))]


async def _clean_certificates(db: AsyncSession, category: str, ids: list[str]) -> list[str]:
    types = await _certificate_types(db, category)
    wanted = list(dict.fromkeys(i.strip().lower() for i in ids))
    if any(i not in types or not types[i].active for i in wanted):
        raise BadRequest("One of the certificates isn't available for this category. Reload the form and retry.")
    return wanted


async def _refuse_leaks(db: AsyncSession, business_id: uuid.UUID, values: dict[str, Any]) -> None:
    """RFQ text must not carry a way to reach the buyer, or the buyer's own name."""
    texts = {f: values.get(f) for f in LEAK_CHECKED if isinstance(values.get(f), str)}
    if not texts:
        return
    found = leakfilter.check_all(texts, await masking.legal_name_for_text_check(db, business_id))
    for field, result in found.items():
        if result.blocked:
            reasons = list(result.reasons)
            what = reasons[0] if len(reasons) == 1 else ", ".join(reasons[:-1]) + " and " + reasons[-1]
            raise BadRequest(
                f"Remove the {what} from the {LEAK_CHECKED[field]}. Sellers reach you through Corridor One X."
            )


# ── Buyer: drafts ────────────────────────────────────────────────────


async def _own(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> Rfq:
    """The caller's own RFQ; anyone else's does not exist for them."""
    rfq = None
    if rfq_id is not None:
        rfq = await db.scalar(select(Rfq).where(Rfq.id == rfq_id, Rfq.buyer_business_id == user.business_id))
    if rfq is None:
        raise NotFound("Request not found.")
    return rfq


async def _apply(db: AsyncSession, rfq: Rfq, changes: dict[str, Any], payload: RfqCreate | RfqUpdate) -> None:
    for field in _BLANK_TO_NONE:
        if field in changes:
            changes[field] = (changes[field] or "").strip() or None
    await _refuse_leaks(db, rfq.buyer_business_id, changes)
    specs = changes.pop("specs", None)
    certificate_ids = changes.pop("certificate_type_ids", None)
    category_changed = "category" in changes and changes["category"] != rfq.category
    for field, value in changes.items():
        setattr(rfq, field, value)
    if rfq.target_price_min is not None and rfq.currency is None:
        raise BadRequest("Choose the currency of your target price.")
    if rfq.target_price_max is not None and (rfq.target_price_min is None or rfq.target_price_max < rfq.target_price_min):
        raise BadRequest("The upper target price can't be below the lower one.")
    if rfq.delivery_from and rfq.delivery_to and rfq.delivery_to < rfq.delivery_from:
        raise BadRequest("The delivery window ends before it starts.")
    if specs is not None:
        rfq.specs = await _clean_specs(db, rfq.category, payload.specs or [])
    elif category_changed:
        rfq.specs = []  # the old rows belong to another template
    if certificate_ids is not None:
        rfq.certificate_type_ids = await _clean_certificates(db, rfq.category, certificate_ids)
    elif category_changed:
        rfq.certificate_type_ids = []


async def create_rfq(db: AsyncSession, user: User, payload: RfqCreate) -> Rfq:
    """A new draft. From a listing it starts with that listing's category and
    name; an open request states its own."""
    changes = payload.model_dump(exclude_unset=True, exclude={"kind", "listing_id"})
    rfq = Rfq(
        id=uuid.uuid4(), buyer_business_id=user.business_id, created_by_user_id=user.id, kind=payload.kind,
        status=R.draft, specs=[], certificate_type_ids=[], incoterms=[],
    )
    if payload.kind == "listing":
        listing = await _visible_listing(db, payload.listing_id)
        if listing.business_id == user.business_id:
            raise BadRequest("This is your own listing.")
        rfq.listing_id = listing.id
        rfq.category = listing.category
        rfq.product_name = changes.pop("product_name", None) or listing.name
        rfq.unit = listing.unit
        changes.pop("category", None)  # the listing decides
    else:
        if not payload.category or not payload.product_name:
            raise BadRequest("Say what you are looking for: a category and a product name.")
        rfq.category = payload.category
        rfq.product_name = payload.product_name
    await _apply(db, rfq, {k: v for k, v in changes.items() if v is not None}, payload)
    db.add(rfq)
    await db.commit()
    await db.refresh(rfq)
    return rfq


async def update_rfq(db: AsyncSession, user: User, rfq_id: uuid.UUID | None, payload: RfqUpdate) -> Rfq:
    rfq = await _own(db, user, rfq_id)
    if rfq.status != R.draft:
        raise Conflict("A request can only be changed before it is submitted.")
    changes = payload.model_dump(include=payload.model_fields_set)
    if rfq.kind == "listing" and "category" in changes and changes["category"] != rfq.category:
        raise BadRequest("A request raised from a listing keeps that listing's category.")
    for field in ("category", "product_name", "unit"):
        if field in changes and changes[field] is None:
            raise BadRequest(f"{field.replace('_', ' ').capitalize()} can't be empty.")
    await _apply(db, rfq, changes, payload)
    await db.commit()
    await db.refresh(rfq)
    return rfq


async def delete_draft(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> None:
    rfq = await _own(db, user, rfq_id)
    if rfq.status != R.draft:
        raise Conflict("Only a draft can be deleted.")
    await db.delete(rfq)
    await db.commit()


async def _visible_listing(db: AsyncSession, listing_id: str | None) -> Product:
    try:
        lid = uuid.UUID(listing_id or "")
    except ValueError:
        raise NotFound("Listing not found.") from None
    listing = await db.scalar(visible_products_select().where(Product.id == lid))
    if listing is None:
        raise NotFound("Listing not found.")
    return listing


async def missing_to_submit(db: AsyncSession, rfq: Rfq, today) -> list[str]:
    """What the buyer still has to add, in plain words."""
    missing = []
    if rfq.quantity is None:
        missing.append("the quantity")
    if not rfq.delivery_country:
        missing.append("the delivery country")
    if rfq.delivery_from is None or rfq.delivery_to is None:
        missing.append("the delivery window")
    elif rfq.delivery_to < today:
        missing.append("a delivery window that is not in the past")
    if not rfq.incoterms:
        missing.append("at least one incoterm")
    if not rfq.payment_terms:
        missing.append("how you would like to pay")
    given = {s["parameter_id"] for s in rfq.specs or []}
    for pid, param in sorted((await _parameters(db, rfq.category)).items(), key=lambda kv: kv[1].sort_order):
        if param.active and param.is_required and pid not in given:
            missing.append(f'your limit for "{param.name}"')
    return missing


# ── Buyer: submit ────────────────────────────────────────────────────


async def submit_cost(db: AsyncSession, user: User) -> SubmitCost:
    """What submitting an RFQ would take from this company right now."""
    wallet = await credits.wallet_view(db, user)
    free = bool(wallet.free_rfqs and wallet.free_rfqs.remaining > 0)
    price = next((p.credits for p in wallet.prices if p.action == "RFQ_POST"), 0)
    return SubmitCost(credits=0 if free else price, free=free)


async def submit_rfq(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> Rfq:
    """Send a draft to the desk. One transaction: the charge, the deal, the
    status and the proposed matches all happen or none do."""
    rfq = await _own(db, user, rfq_id)
    if not user.business.is_verified:
        raise Forbidden("Get your business verified before submitting a request. Your draft is saved.")
    if rfq.status != R.draft:
        _move(rfq, R.submitted)  # raises the right Conflict
    now = utcnow()
    missing = await missing_to_submit(db, rfq, now.date())
    if missing:
        raise BadRequest("Before submitting, add " + _join(missing) + ".")
    held = await _held_reason(db, rfq, user.business)

    await credits.spend(db, user, "RFQ_POST", idempotency_key=spend_key(rfq.id), reference=("rfq", str(rfq.id)))
    deal = await machine.open_deal(db, user.business_id, Actor.user(user.id))
    await db.flush()
    rfq.deal_id = deal.id
    rfq.submitted_at = now
    rfq.expires_at = now + timedelta(days=int(await setting(db, seed.RFQ_OPEN_DAYS)))
    if held:
        _move(rfq, R.held)
        rfq.desk_reason = held
    else:
        _move(rfq, R.submitted)
    await propose_matches(db, rfq, today=now.date())
    await db.commit()
    await db.refresh(rfq)
    return rfq


async def _held_reason(db: AsyncSession, rfq: Rfq, buyer: Business) -> str | None:
    """Why this RFQ must stop for a compliance look, if it must (A-039)."""
    codes = {c for c in (rfq.delivery_country, buyer.country) if c}
    held = list(await db.scalars(select(HeldCountry).where(HeldCountry.code.in_(codes)).order_by(HeldCountry.code)))
    if not held:
        return None
    return "; ".join(f"{h.code}: {h.reason}" for h in held)[:500]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ── Matching ─────────────────────────────────────────────────────────


async def _required_names(db: AsyncSession, category: str) -> dict[str, str]:
    return {pid: p.name for pid, p in (await _parameters(db, category)).items() if p.is_required}


async def evaluate_listing(db: AsyncSession, rfq: Rfq, listing: Product, today) -> list[dict[str, Any]]:
    specs = (await catalog._stored_specs(db, [listing.id]))[listing.id]
    return matching.evaluate(rfq, listing, specs, await _required_names(db, rfq.category), today)


async def propose_matches(db: AsyncSession, rfq: Rfq, *, today) -> int:
    """Replace the rule-made proposals with a fresh run. Desk-added and
    confirmed matches are left alone. One listing per seller: the first that
    passes. A request raised from a listing proposes that listing only."""
    stmt = visible_products_select().where(
        Product.category == rfq.category, Product.business_id != rfq.buyer_business_id
    )
    if rfq.kind == "listing":
        stmt = stmt.where(Product.id == rfq.listing_id)
    listings = list(await db.scalars(stmt.order_by(Product.published_at.desc())))
    specs = await catalog._stored_specs(db, [p.id for p in listings])
    required = await _required_names(db, rfq.category)

    existing = {m.seller_business_id: m for m in await db.scalars(select(RfqMatch).where(RfqMatch.rfq_id == rfq.id))}
    for match in existing.values():
        if match.source == "rule" and match.status == "proposed":
            await db.delete(match)
    await db.flush()
    kept = {seller for seller, m in existing.items() if not (m.source == "rule" and m.status == "proposed")}

    proposed = 0
    for listing in listings:
        if proposed >= MAX_PROPOSALS:
            break
        if listing.business_id in kept:
            continue
        reasons = matching.evaluate(rfq, listing, specs[listing.id], required, today)
        if matching.passes(reasons):
            db.add(RfqMatch(
                rfq_id=rfq.id, seller_business_id=listing.business_id, listing_id=listing.id, status="proposed",
                source="rule", reasons=reasons,
            ))
            kept.add(listing.business_id)
            proposed += 1
    return proposed


# ── Views ────────────────────────────────────────────────────────────


async def seller_view(db: AsyncSession, rfq: Rfq) -> RfqSellerView:
    """The RFQ as a seller reads it: no target price, no buyer name."""
    params = await _parameters(db, rfq.category)
    types = await _certificate_types(db, rfq.category)
    buyer = await db.get(Business, rfq.buyer_business_id)
    deal_code = await db.scalar(select(Deal.code).where(Deal.id == rfq.deal_id)) if rfq.deal_id else None
    return RfqSellerView(
        id=str(rfq.id),
        deal_code=deal_code,
        buyer_code=buyer.company_code if buyer else None,
        buyer_country=buyer.country if buyer else None,
        category=rfq.category,
        product_name=rfq.product_name,
        variety=rfq.variety,
        grade=rfq.grade,
        specs=[
            SpecLimitOut(
                parameter_id=s["parameter_id"], code=params[s["parameter_id"]].code,
                name=params[s["parameter_id"]].name, unit=params[s["parameter_id"]].unit, value=s["value"],
                operator=s["operator"],
            )
            for s in rfq.specs or []
            if s["parameter_id"] in params
        ],
        quantity=rfq.quantity,
        unit=rfq.unit,
        packaging=rfq.packaging,
        certificates=[
            CertificateNeed(certificate_type_id=i, name=types[i].name) for i in rfq.certificate_type_ids or [] if i in types
        ],
        incoterms=list(rfq.incoterms or []),
        payment_terms=rfq.payment_terms,
        delivery_country=rfq.delivery_country,
        destination_port=rfq.destination_port,
        delivery_from=rfq.delivery_from,
        delivery_to=rfq.delivery_to,
        notes=rfq.notes,
        expires_at=rfq.expires_at,
    )


def tracking(rfq: Rfq, deal_status: str | None) -> str:
    """The one word the buyer's list shows (plan: Awaiting / Quoted / Expired)."""
    if rfq.status in (R.draft, R.rejected, R.unmatched, R.expired):
        return rfq.status
    if deal_status and deal_status != D.RFQ_OPEN:
        return "quoted" if deal_status != D.CANCELLED else "cancelled"
    return "awaiting"


async def to_read(db: AsyncSession, rfq: Rfq) -> RfqRead:
    view = await seller_view(db, rfq)
    deal_status = await db.scalar(select(Deal.status).where(Deal.id == rfq.deal_id)) if rfq.deal_id else None
    return RfqRead(
        **view.model_dump(),
        kind=rfq.kind,
        listing_id=str(rfq.listing_id) if rfq.listing_id else None,
        status=rfq.status,
        tracking=tracking(rfq, deal_status),
        target_price_min=rfq.target_price_min,
        target_price_max=rfq.target_price_max,
        currency=rfq.currency,
        missing=await missing_to_submit(db, rfq, utcnow().date()) if rfq.status == R.draft else [],
        rejection_reason=rfq.desk_reason if rfq.status == R.rejected else None,
        submitted_at=rfq.submitted_at,
        created_at=rfq.created_at,
    )


async def get_own(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> Rfq:
    return await _own(db, user, rfq_id)


async def list_own(db: AsyncSession, user: User, *, limit: int, offset: int) -> tuple[int, list[Rfq]]:
    """The company's requests, newest first."""
    await expire_due(db)
    mine = Rfq.buyer_business_id == user.business_id
    total = await db.scalar(select(func.count(Rfq.id)).where(mine)) or 0
    rows = await db.scalars(select(Rfq).where(mine).order_by(Rfq.created_at.desc()).offset(offset).limit(limit))
    return total, list(rows)


# ── Seller inbox ─────────────────────────────────────────────────────


def _inbox_stmt(user: User):
    return (
        select(RfqMatch, Rfq)
        .join(Rfq, Rfq.id == RfqMatch.rfq_id)
        .where(
            RfqMatch.seller_business_id == user.business_id, RfqMatch.status == "confirmed", Rfq.status == R.matched
        )
    )


async def list_matched(db: AsyncSession, user: User, *, limit: int, offset: int) -> tuple[int, list[MatchedRfqRow]]:
    """Requests the desk matched to this company and that are still open.
    The row is free to read; opening one is what costs credits."""
    await expire_due(db)
    stmt = _inbox_stmt(user)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(RfqMatch.confirmed_at.desc()).offset(offset).limit(limit))).all()
    cost = await credits.price_of(db, "RFQ_VIEW")
    return total, [
        MatchedRfqRow(
            id=str(rfq.id), category=rfq.category, product_name=rfq.product_name, quantity=rfq.quantity,
            unit=rfq.unit, delivery_country=rfq.delivery_country, delivery_to=rfq.delivery_to,
            expires_at=rfq.expires_at, opened=match.viewed_at is not None,
            open_cost=0 if match.viewed_at else cost, matched_at=match.confirmed_at,
        )
        for match, rfq in rows
    ]


async def matched_for(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> tuple[RfqMatch, Rfq]:
    """This seller's confirmed match on an open RFQ; otherwise it is not theirs to see."""
    row = None
    if rfq_id is not None:
        row = (await db.execute(_inbox_stmt(user).where(Rfq.id == rfq_id))).first()
    if row is None:
        raise NotFound("Request not found.")
    return row[0], row[1]


async def open_matched(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> RfqSellerView:
    """Open a matched RFQ. The first opening debits RFQ_VIEW; later ones are
    free, and a retry of the first charges once."""
    await expire_due(db)
    match, rfq = await matched_for(db, user, rfq_id)
    if match.viewed_at is None:
        await credits.spend(db, user, "RFQ_VIEW", idempotency_key=view_key(match.id), reference=("rfq", str(rfq.id)))
        match.viewed_at = utcnow()
        await db.commit()
    return await seller_view(db, rfq)


# ── Expiry ───────────────────────────────────────────────────────────


async def expire_due(db: AsyncSession, now: datetime | None = None) -> int:
    """Close every RFQ whose open period ran out without an offer: the RFQ
    becomes ``expired`` and its deal is cancelled. Safe to call often; it is
    run before the lists are read and by ``scripts/expire_rfqs.py``."""
    now = now or utcnow()
    due = list(await db.scalars(
        select(Rfq).where(Rfq.status.in_((R.submitted, R.held, R.matched)), Rfq.expires_at < now)
    ))
    closed = 0
    for rfq in due:
        deal = await db.get(Deal, rfq.deal_id)
        if deal is None or deal.status != D.RFQ_OPEN:
            continue  # an offer was published; the deal has moved on
        _move(rfq, R.expired)
        machine.transition(db, deal, D.CANCELLED, actor=Actor.system(), reason="expired")
        closed += 1
    if closed:
        await db.commit()
    return closed


# ── Desk ─────────────────────────────────────────────────────────────


async def _desk_rfq(db: AsyncSession, rfq_id: uuid.UUID | None) -> Rfq:
    rfq = await db.get(Rfq, rfq_id) if rfq_id else None
    if rfq is None or rfq.status == R.draft:
        raise NotFound("Request not found.")  # a draft is the buyer's alone
    return rfq


async def desk_list(db: AsyncSession, *, queue: str, limit: int, offset: int) -> tuple[int, list[DeskRfqRow]]:
    """``queue=pending``: waiting on the desk, oldest first. ``queue=all``:
    every submitted RFQ, newest first."""
    await expire_due(db)
    stmt = select(Rfq).where(Rfq.status != R.draft)
    if queue == "pending":
        stmt = stmt.where(Rfq.status.in_(R.QUEUE))
        order = (Rfq.submitted_at.asc(),)
    else:
        order = (Rfq.submitted_at.desc(),)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rfqs = list(await db.scalars(stmt.order_by(*order).offset(offset).limit(limit)))
    ids = [r.id for r in rfqs]
    counts: dict[tuple[uuid.UUID, str], int] = {}
    if ids:
        for rid, status, n in await db.execute(
            select(RfqMatch.rfq_id, RfqMatch.status, func.count()).where(RfqMatch.rfq_id.in_(ids)).group_by(
                RfqMatch.rfq_id, RfqMatch.status
            )
        ):
            counts[(rid, status)] = n
    buyers = await _businesses(db, [r.buyer_business_id for r in rfqs])
    deals = await _deal_codes(db, [r.deal_id for r in rfqs if r.deal_id])
    return total, [
        DeskRfqRow(
            id=str(r.id), deal_code=deals.get(r.deal_id), buyer_code=_code(buyers.get(r.buyer_business_id)),
            category=r.category, product_name=r.product_name, quantity=r.quantity, unit=r.unit,
            delivery_country=r.delivery_country, status=r.status, submitted_at=r.submitted_at,
            expires_at=r.expires_at, proposed=counts.get((r.id, "proposed"), 0),
            confirmed=counts.get((r.id, "confirmed"), 0),
        )
        for r in rfqs
    ]


async def _businesses(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, Business]:
    if not ids:
        return {}
    return {b.id: b for b in await db.scalars(select(Business).where(Business.id.in_(set(ids))))}


async def _deal_codes(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict((await db.execute(select(Deal.id, Deal.code).where(Deal.id.in_(set(ids))))).all())


def _code(business: Business | None) -> str | None:
    return business.company_code if business else None


async def desk_detail(db: AsyncSession, rfq_id: uuid.UUID | None) -> DeskRfqDetail:
    """Everything the desk needs on one RFQ. Parties appear as company codes;
    turning a code into a name is the audited unmask, not this screen."""
    rfq = await _desk_rfq(db, rfq_id)
    matches = list(await db.scalars(
        select(RfqMatch).where(RfqMatch.rfq_id == rfq.id, RfqMatch.status != "removed").order_by(RfqMatch.created_at)
    ))
    sellers = await _businesses(db, [m.seller_business_id for m in matches])
    listing_ids = [m.listing_id for m in matches if m.listing_id]
    names = dict((await db.execute(select(Product.id, Product.name).where(Product.id.in_(listing_ids)))).all()) if listing_ids else {}
    flags = [
        DeskLeakFlag(field=field, reasons=list(result.reasons))
        for field, result in leakfilter.check_all({f: getattr(rfq, f) for f in LEAK_CHECKED}).items()
    ]
    return DeskRfqDetail(
        rfq=await seller_view(db, rfq),
        kind=rfq.kind,
        status=rfq.status,
        target_price_min=rfq.target_price_min,
        target_price_max=rfq.target_price_max,
        currency=rfq.currency,
        desk_reason=rfq.desk_reason,
        submitted_at=rfq.submitted_at,
        matches=[
            MatchOut(
                id=str(m.id), seller_code=_code(sellers.get(m.seller_business_id)),
                seller_state=sellers[m.seller_business_id].state if m.seller_business_id in sellers else None,
                listing_id=str(m.listing_id) if m.listing_id else None, listing_name=names.get(m.listing_id),
                status=m.status, source=m.source, reasons=[MatchReason(**r) for r in m.reasons],
                viewed_at=m.viewed_at,
            )
            for m in matches
        ],
        leak_flags=flags,
    )


async def _open_for_desk(db: AsyncSession, rfq_id: uuid.UUID | None) -> Rfq:
    rfq = await _desk_rfq(db, rfq_id)
    if rfq.status != R.submitted:
        raise Conflict(f"This request is {_LABEL.get(rfq.status, rfq.status)}, so its matches can't be changed.")
    return rfq


async def desk_rematch(db: AsyncSession, rfq_id: uuid.UUID | None) -> Rfq:
    """Run the rules again, for listings published since the RFQ came in."""
    rfq = await _open_for_desk(db, rfq_id)
    await propose_matches(db, rfq, today=utcnow().date())
    return rfq


async def desk_add_match(db: AsyncSession, rfq_id: uuid.UUID | None, listing_id: str) -> RfqMatch:
    """Add a seller the rules did not propose. The listing must still meet
    every hard rule: the desk adjusts the choice, not the rules."""
    rfq = await _open_for_desk(db, rfq_id)
    listing = await _visible_listing(db, listing_id)
    if listing.business_id == rfq.buyer_business_id:
        raise BadRequest("That listing belongs to the buyer.")
    reasons = await evaluate_listing(db, rfq, listing, utcnow().date())
    failed = [r["detail"] for r in reasons if not r["ok"]]
    if failed:
        raise Conflict("That listing doesn't meet the request: " + " ".join(failed))
    match = await db.scalar(
        select(RfqMatch).where(RfqMatch.rfq_id == rfq.id, RfqMatch.seller_business_id == listing.business_id)
    )
    if match is not None and match.status != "removed":
        raise Conflict("That seller is already matched to this request.")
    if match is None:
        match = RfqMatch(rfq_id=rfq.id, seller_business_id=listing.business_id)
        db.add(match)
    match.listing_id, match.status, match.source, match.reasons = listing.id, "proposed", "desk", reasons
    await db.flush()
    return match


async def desk_remove_match(db: AsyncSession, rfq_id: uuid.UUID | None, match_id: uuid.UUID | None) -> RfqMatch:
    rfq = await _open_for_desk(db, rfq_id)
    match = await db.get(RfqMatch, match_id) if match_id else None
    if match is None or match.rfq_id != rfq.id or match.status == "removed":
        raise NotFound("Match not found.")
    match.status = "removed"
    return match


async def desk_confirm(db: AsyncSession, admin_id: uuid.UUID, rfq_id: uuid.UUID | None) -> tuple[Rfq, list[uuid.UUID]]:
    """Confirm the proposed matches: from here the matched sellers can see
    the RFQ. Returns the RFQ and the seller businesses to notify."""
    rfq = await _open_for_desk(db, rfq_id)
    proposed = list(await db.scalars(select(RfqMatch).where(RfqMatch.rfq_id == rfq.id, RfqMatch.status == "proposed")))
    if not proposed:
        raise Conflict("There is no seller to confirm. Add one, or close the request as unmatched.")
    now = utcnow()
    for match in proposed:
        match.status, match.confirmed_at, match.confirmed_by = "confirmed", now, admin_id
    _move(rfq, R.matched)
    rfq.decided_at, rfq.decided_by = now, admin_id
    return rfq, [m.seller_business_id for m in proposed]


async def desk_close(
    db: AsyncSession, admin_id: uuid.UUID, rfq_id: uuid.UUID | None, *, to: str, reason: str
) -> tuple[Rfq, Deal]:
    """Reject an RFQ, or close it as unmatched: refund the buyer and cancel
    the deal (A-038). ``to`` is ``rejected`` or ``unmatched``."""
    rfq = await _desk_rfq(db, rfq_id)
    _move(rfq, to)
    now = utcnow()
    rfq.decided_at, rfq.decided_by = now, admin_id
    if to == R.rejected:
        rfq.desk_reason = reason
    deal = await db.get(Deal, rfq.deal_id)
    machine.transition(
        db, deal, D.CANCELLED, actor=Actor.admin(admin_id),
        reason="RFQ rejected by the desk" if to == R.rejected else "No seller matched the request",
    )
    await credits.refund(
        db, rfq.buyer_business_id, spend_key(rfq.id),
        note="Request rejected" if to == R.rejected else "No seller matched",
    )
    return rfq, deal


async def desk_hold(db: AsyncSession, rfq_id: uuid.UUID | None, reason: str) -> Rfq:
    rfq = await _desk_rfq(db, rfq_id)
    _move(rfq, R.held)
    rfq.desk_reason = reason
    return rfq


async def desk_release(db: AsyncSession, rfq_id: uuid.UUID | None) -> Rfq:
    """Put a held RFQ back in the queue once it has been looked at."""
    rfq = await _desk_rfq(db, rfq_id)
    if rfq.status != R.held:
        raise Conflict("Only a request on hold can be released.")
    _move(rfq, R.submitted)
    rfq.desk_reason = None
    return rfq


async def deal_status_of(db: AsyncSession, rfq: Rfq) -> str | None:
    return await db.scalar(select(Deal.status).where(Deal.id == rfq.deal_id)) if rfq.deal_id else None


# ── Desk configuration ───────────────────────────────────────────────


async def list_held(db: AsyncSession) -> list[HeldCountry]:
    return list(await db.scalars(select(HeldCountry).order_by(HeldCountry.code)))


async def hold_country(db: AsyncSession, code: str, reason: str) -> HeldCountry:
    code = code.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise BadRequest("Use the two-letter country code.")
    row = await db.get(HeldCountry, code)
    if row is None:
        row = HeldCountry(code=code, reason=reason)
        db.add(row)
    row.reason = reason
    return row


async def release_country(db: AsyncSession, code: str) -> None:
    row = await db.get(HeldCountry, code.strip().upper())
    if row is None:
        raise NotFound("That country is not on the list.")
    await db.delete(row)


async def list_settings(db: AsyncSession) -> list[TradeSetting]:
    return list(await db.scalars(select(TradeSetting).order_by(TradeSetting.key)))


async def set_setting(db: AsyncSession, key: str, value: Decimal) -> tuple[TradeSetting, Decimal]:
    row = await db.get(TradeSetting, key)
    if row is None:
        raise NotFound("No such setting.")
    if key.endswith("_days") and (value != value.to_integral_value() or value < 1):
        raise BadRequest("Enter a whole number of days, one or more.")
    old = Decimal(row.value)
    row.value = value
    row.is_placeholder = False
    return row, old
