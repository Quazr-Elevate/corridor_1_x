"""Quote, cost sheet and offer rules (build plan 06).

* A matched seller who has opened the RFQ quotes once and may revise the
  quote until the desk starts a cost sheet on it. A quote must answer every
  required specification the buyer set a limit on.
* The cost sheet converts once, at a rate and buffer stored on the sheet. A
  freight figure older than the allowed age is refused. A margin under the
  floor needs a desk manager who is not the sheet's author.
* Publishing a ready sheet creates the offer and moves the deal to QUOTED on
  the first one. The offer ends at least two days before the quote does.
* A buyer sees the offer's lead time, incoterm and specs met for free, and
  the price after paying OFFER_UNLOCK once. No buyer route ever returns a
  quote, a cost sheet or the purchase price.

Minor-unit arithmetic assumes two-decimal currencies on both sides, which
holds for every supported currency (INR, AED, USD).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.business import Business
from app.models.deal import Deal
from app.models.deal import DealStatus as D
from app.models.quote import COST_LINES, CostSheet, Offer, OfferUnlock, Quote
from app.models.rfq import Rfq, RfqMatch
from app.models.rfq import RfqStatus as R
from app.models.user import User
from app.modules.credits import service as credits
from app.modules.deals import machine
from app.modules.deals.machine import Actor
from app.modules.fx import service as fx
from app.modules.masking import service as masking
from app.modules.quotes.schemas import (
    CostSheetIn,
    CostSheetRead,
    DeskQuote,
    OfferRead,
    QuoteIn,
    QuoteRead,
    SpecAnswerOut,
)
from app.modules.rfq import seed
from app.modules.rfq import service as rfqs
from app.shared import leakfilter

#: An offer must end this many days before the quote behind it (plan 6.4).
OFFER_GAP_DAYS = 2
#: Cross-border deals are priced in this currency (plan 10.4).
CROSS_BORDER_CURRENCY = "USD"


def _pct(value: Decimal) -> Decimal:
    """A percentage as the column stores it: two decimal places."""
    return Decimal(value).quantize(Decimal("0.01"))


def _rate(value: Decimal) -> Decimal:
    """An FX rate as the column stores it: eight decimal places."""
    return Decimal(value).quantize(Decimal("0.00000001"))


def unlock_key(offer_id: uuid.UUID, business_id: uuid.UUID) -> str:
    return f"offer_unlock:{offer_id}:{business_id}"


# ── Seller: quote ────────────────────────────────────────────────────


async def _required_limits(db: AsyncSession, rfq: Rfq) -> dict[str, str]:
    """Parameter id → name, for the required specs this RFQ sets a limit on."""
    required = await rfqs._required_names(db, rfq.category)
    return {s["parameter_id"]: required[s["parameter_id"]] for s in rfq.specs or [] if s["parameter_id"] in required}


async def save_quote(db: AsyncSession, user: User, rfq_id: uuid.UUID | None, payload: QuoteIn) -> Quote:
    """Create this seller's quote on a matched RFQ, or revise it."""
    await rfqs.expire_due(db)
    match, rfq = await rfqs.matched_for(db, user, rfq_id)
    if match.viewed_at is None:
        raise Conflict("Open the request before quoting on it.")
    today = utcnow().date()
    valid_until = payload.valid_until or today + timedelta(days=int(await rfqs.setting(db, seed.QUOTE_VALID_DAYS)))
    if valid_until < today + timedelta(days=OFFER_GAP_DAYS):
        raise BadRequest(f"A quote must stay valid for at least {OFFER_GAP_DAYS} more days.")
    if payload.incoterm not in (rfq.incoterms or []):
        raise BadRequest("Quote on one of the incoterms the buyer accepts: " + ", ".join(rfq.incoterms or []) + ".")
    if payload.unit != rfq.unit:
        raise BadRequest(f"Quote per {rfq.unit}, the unit the buyer asked in.")
    notes = (payload.notes or "").strip() or None
    port = (payload.port_of_loading or "").strip() or None
    own_name = await masking.legal_name_for_text_check(db, user.business_id)
    for label, value in (("notes", notes), ("port of loading", port)):
        found = leakfilter.check(value, own_name)
        if found.blocked:
            raise BadRequest(f"Remove the {' and '.join(found.reasons)} from the {label}. Buyers reach you through Corridor One X.")

    needed = await _required_limits(db, rfq)
    answers = {a.parameter_id.strip().lower(): a for a in payload.specs}
    missing = [name for pid, name in needed.items() if pid not in answers]
    if missing:
        raise BadRequest("Say whether you meet each required specification. Missing: " + ", ".join(missing) + ".")
    specs = [
        {"parameter_id": pid, "meets": answers[pid].meets, "value": (answers[pid].value or "").strip() or None}
        for pid in needed
    ]

    quote = await db.scalar(select(Quote).where(Quote.match_id == match.id))
    if quote is None:
        quote = Quote(rfq_id=rfq.id, match_id=match.id, seller_business_id=user.business_id, created_by_user_id=user.id)
        db.add(quote)
    elif await _sheet_of(db, quote.id) is not None:
        raise Conflict("Corridor One X is already working on this quote, so it can no longer be changed.")
    quote.price_minor, quote.currency = payload.price_minor, fx.ensure_supported(payload.currency, what="Quote currency")
    quote.quantity, quote.unit = payload.quantity, payload.unit
    quote.incoterm, quote.port_of_loading = payload.incoterm, port
    quote.lead_time_days, quote.payment_terms = payload.lead_time_days, list(dict.fromkeys(payload.payment_terms))
    quote.valid_until, quote.specs, quote.notes = valid_until, specs, notes
    quote.updated_at = utcnow()
    try:
        await db.commit()
    except IntegrityError:  # two saves at once on the same match
        await db.rollback()
        raise Conflict("This quote was just saved from another window. Reload and try again.") from None
    await db.refresh(quote)
    return quote


async def own_quote(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> Quote:
    quote = None
    if rfq_id is not None:
        quote = await db.scalar(
            select(Quote).where(Quote.rfq_id == rfq_id, Quote.seller_business_id == user.business_id)
        )
    if quote is None:
        raise NotFound("Quote not found.")
    return quote


async def _answers_out(db: AsyncSession, rfq_id: uuid.UUID, specs: list) -> list[SpecAnswerOut]:
    rfq = await db.get(Rfq, rfq_id)
    names = await rfqs._required_names(db, rfq.category) if rfq else {}
    return [
        SpecAnswerOut(parameter_id=s["parameter_id"], name=names.get(s["parameter_id"], "Specification"), meets=s["meets"], value=s.get("value"))
        for s in specs or []
    ]


async def quote_to_read(db: AsyncSession, quote: Quote) -> QuoteRead:
    return QuoteRead(
        id=str(quote.id), rfq_id=str(quote.rfq_id), price_minor=quote.price_minor, currency=quote.currency,
        quantity=quote.quantity, unit=quote.unit, incoterm=quote.incoterm, port_of_loading=quote.port_of_loading,
        lead_time_days=quote.lead_time_days, payment_terms=list(quote.payment_terms), valid_until=quote.valid_until,
        specs=await _answers_out(db, quote.rfq_id, quote.specs), notes=quote.notes,
        editable=await _sheet_of(db, quote.id) is None, updated_at=quote.updated_at,
    )


# ── Desk: cost sheet ─────────────────────────────────────────────────


async def _sheet_of(db: AsyncSession, quote_id: uuid.UUID) -> CostSheet | None:
    return await db.scalar(select(CostSheet).where(CostSheet.quote_id == quote_id))


async def _desk_quote(db: AsyncSession, quote_id: uuid.UUID | None) -> tuple[Quote, Rfq]:
    quote = await db.get(Quote, quote_id) if quote_id else None
    if quote is None:
        raise NotFound("Quote not found.")
    return quote, await db.get(Rfq, quote.rfq_id)


def total_cost(sheet: CostSheet) -> int:
    return sheet.purchase_price_minor + sum(getattr(sheet, f"{line}_minor") for line in COST_LINES)


def sell_price(total_minor: int, fx_rate: Decimal, buffer_pct: Decimal, margin_pct: Decimal) -> int:
    """Cost → selling price, per unit, in the deal currency. Rounded up to
    the minor unit so rounding never eats the margin."""
    converted = Decimal(total_minor) * fx_rate * (1 + buffer_pct / 100)
    return int((converted * (1 + margin_pct / 100)).to_integral_value(rounding=ROUND_CEILING))


async def save_cost_sheet(
    db: AsyncSession, admin_id: uuid.UUID, quote_id: uuid.UUID | None, payload: CostSheetIn
) -> CostSheet:
    """Create or rework the sheet on a quote. Reworking clears any approval:
    the numbers that were approved are no longer the numbers."""
    quote, rfq = await _desk_quote(db, quote_id)
    if rfq.status != R.matched:
        raise Conflict("This request is no longer open, so its quotes can't be costed.")
    today = utcnow().date()
    if quote.valid_until < today:
        raise Conflict("This quote has run out. Ask the seller for a fresh one.")
    freight = payload.inland_freight_minor + payload.ocean_freight_minor
    max_age = int(await rfqs.setting(db, seed.FREIGHT_MAX_AGE_DAYS))
    if freight > 0:
        if payload.freight_quoted_on is None:
            raise BadRequest("Enter the day the freight was quoted.")
        if payload.freight_quoted_on > today:
            raise BadRequest("The freight quote date can't be in the future.")
        if (today - payload.freight_quoted_on).days > max_age:
            raise BadRequest(f"That freight quote is more than {max_age} days old. Get a current one.")

    sheet = await _sheet_of(db, quote.id)
    is_new = sheet is None
    if is_new:
        # Added to the session only once every column is set (see the end).
        sheet = CostSheet(quote_id=quote.id, deal_id=rfq.deal_id, created_by=admin_id)
    elif sheet.status == "published":
        raise Conflict("This sheet's offer is already with the buyer.")
    sheet.created_by = admin_id  # whoever last set the numbers is the author an approver must differ from
    sheet.approved_by = sheet.approved_at = None
    sheet.purchase_currency, sheet.purchase_price_minor = quote.currency, quote.price_minor
    for line in COST_LINES:
        setattr(sheet, f"{line}_minor", getattr(payload, f"{line}_minor"))
    sheet.freight_quoted_on = payload.freight_quoted_on if freight > 0 else None

    buyer = await db.get(Business, rfq.buyer_business_id)
    seller = await db.get(Business, quote.seller_business_id)
    sheet.deal_currency = CROSS_BORDER_CURRENCY if buyer.country != seller.country else quote.currency
    if sheet.deal_currency == sheet.purchase_currency:
        sheet.fx_rate, sheet.fx_as_of, sheet.fx_buffer_pct = _rate(Decimal(1)), None, _pct(Decimal(0))
    else:
        rates = await fx.get_latest_rates(db)
        rate = fx.convert(Decimal(1), sheet.purchase_currency, sheet.deal_currency, rates)
        if rate is None:
            raise Conflict(f"There is no exchange rate for {sheet.purchase_currency} yet. Refresh the rates and retry.")
        sheet.fx_rate = _rate(rate)
        sheet.fx_as_of = rates.as_of_by.get(sheet.purchase_currency) or rates.as_of_by.get(sheet.deal_currency)
        sheet.fx_buffer_pct = _pct(await rfqs.setting(db, seed.FX_BUFFER_PCT))
    sheet.margin_pct = _pct(payload.margin_pct)
    sheet.min_margin_pct = _pct(await rfqs.setting(db, seed.MIN_MARGIN_PCT))
    sheet.sell_price_minor = sell_price(total_cost(sheet), sheet.fx_rate, sheet.fx_buffer_pct, sheet.margin_pct)
    sheet.status = "pending_approval" if sheet.margin_pct < sheet.min_margin_pct else "ready"
    sheet.updated_at = utcnow()
    if is_new:
        db.add(sheet)
    await db.flush()
    return sheet


async def approve_cost_sheet(db: AsyncSession, admin_id: uuid.UUID, sheet_id: uuid.UUID | None) -> CostSheet:
    """A desk manager accepts a margin under the floor. Not their own sheet."""
    sheet = await db.get(CostSheet, sheet_id) if sheet_id else None
    if sheet is None:
        raise NotFound("Cost sheet not found.")
    if sheet.status != "pending_approval":
        raise Conflict("This sheet is not waiting for an approval.")
    if sheet.created_by == admin_id:
        raise Forbidden("Someone other than the sheet's author has to approve a margin under the floor.")
    sheet.approved_by, sheet.approved_at, sheet.status = admin_id, utcnow(), "ready"
    return sheet


def sheet_to_read(sheet: CostSheet) -> CostSheetRead:
    return CostSheetRead(
        id=str(sheet.id), quote_id=str(sheet.quote_id), status=sheet.status,
        purchase_currency=sheet.purchase_currency, purchase_price_minor=sheet.purchase_price_minor,
        **{f"{line}_minor": getattr(sheet, f"{line}_minor") for line in COST_LINES},
        freight_quoted_on=sheet.freight_quoted_on, total_cost_minor=total_cost(sheet),
        deal_currency=sheet.deal_currency, fx_rate=sheet.fx_rate, fx_as_of=sheet.fx_as_of,
        fx_buffer_pct=sheet.fx_buffer_pct, margin_pct=sheet.margin_pct, min_margin_pct=sheet.min_margin_pct,
        sell_price_minor=sheet.sell_price_minor, needs_approval=sheet.status == "pending_approval",
        approved=sheet.approved_by is not None,
    )


async def desk_quotes(db: AsyncSession, rfq_id: uuid.UUID | None) -> list[DeskQuote]:
    """Every quote on an RFQ, oldest first, each with its sheet and offer."""
    rfq = await rfqs._desk_rfq(db, rfq_id)
    quotes = list(await db.scalars(select(Quote).where(Quote.rfq_id == rfq.id).order_by(Quote.created_at)))
    sellers = await rfqs._businesses(db, [q.seller_business_id for q in quotes])
    out = []
    for q in quotes:
        sheet = await _sheet_of(db, q.id)
        offer_id = await db.scalar(select(Offer.id).where(Offer.quote_id == q.id))
        seller = sellers.get(q.seller_business_id)
        out.append(DeskQuote(
            id=str(q.id), seller_code=seller.company_code if seller else None, seller_state=seller.state if seller else None,
            price_minor=q.price_minor, currency=q.currency, quantity=q.quantity, unit=q.unit, incoterm=q.incoterm,
            port_of_loading=q.port_of_loading, lead_time_days=q.lead_time_days, payment_terms=list(q.payment_terms),
            valid_until=q.valid_until, specs=await _answers_out(db, q.rfq_id, q.specs), notes=q.notes,
            cost_sheet=sheet_to_read(sheet) if sheet else None, offer_id=str(offer_id) if offer_id else None,
        ))
    return out


# ── Desk: publish ────────────────────────────────────────────────────


async def publish_offer(
    db: AsyncSession, admin_id: uuid.UUID, sheet_id: uuid.UUID | None, valid_until: date | None
) -> tuple[Offer, Deal]:
    """Turn a ready sheet into the buyer's offer. The first offer on a deal
    moves it from RFQ_OPEN to QUOTED."""
    sheet = await db.get(CostSheet, sheet_id) if sheet_id else None
    if sheet is None:
        raise NotFound("Cost sheet not found.")
    if sheet.status == "published":
        raise Conflict("This sheet's offer is already with the buyer.")
    if sheet.status != "ready":
        raise Conflict("A margin under the floor needs a desk manager's approval before the offer goes out.")
    quote, rfq = await _desk_quote(db, sheet.quote_id)
    today = utcnow().date()
    latest = quote.valid_until - timedelta(days=OFFER_GAP_DAYS)
    valid_until = valid_until or latest
    if valid_until > latest:
        raise BadRequest(f"The offer has to end by {latest.isoformat()}, {OFFER_GAP_DAYS} days before the quote does.")
    if valid_until < today:
        raise Conflict("The quote is too close to running out to offer. Ask the seller for a fresh one.")
    deal = await db.get(Deal, sheet.deal_id)
    if deal.status not in (D.RFQ_OPEN, D.QUOTED):
        raise Conflict("This deal has moved on, so no new offer can be published.")

    offer = Offer(
        deal_id=deal.id, rfq_id=rfq.id, quote_id=quote.id, cost_sheet_id=sheet.id,
        buyer_business_id=rfq.buyer_business_id, seller_business_id=quote.seller_business_id, status="published",
        price_minor=sheet.sell_price_minor, currency=sheet.deal_currency, quantity=quote.quantity, unit=quote.unit,
        incoterm=quote.incoterm, port_of_loading=quote.port_of_loading, lead_time_days=quote.lead_time_days,
        payment_terms=list(quote.payment_terms), specs_met=sum(1 for s in quote.specs if s["meets"]),
        specs_total=len(quote.specs), valid_until=valid_until, published_by=admin_id, published_at=utcnow(),
    )
    db.add(offer)
    sheet.status = "published"
    if deal.status == D.RFQ_OPEN:
        machine.transition(db, deal, D.QUOTED, actor=Actor.admin(admin_id), details={"quote_id": str(quote.id)})
    await db.flush()
    return offer, deal


# ── Buyer: offers ────────────────────────────────────────────────────


async def _expire_offers(db: AsyncSession, rfq_id: uuid.UUID) -> None:
    """An offer past its date is marked expired the next time it is read."""
    today = utcnow().date()
    stale = list(await db.scalars(
        select(Offer).where(Offer.rfq_id == rfq_id, Offer.status == "published", Offer.valid_until < today)
    ))
    for offer in stale:
        offer.status = "expired"
    if stale:
        await db.commit()


async def _offer_out(db: AsyncSession, offer: Offer, unlocked: bool, cost: int, seller: Business | None) -> OfferRead:
    out = OfferRead(
        id=str(offer.id), seller_code=seller.company_code if seller else None, seller_state=seller.state if seller else None,
        incoterm=offer.incoterm, lead_time_days=offer.lead_time_days, specs_met=offer.specs_met,
        specs_total=offer.specs_total, valid_until=offer.valid_until, status=offer.status, unlocked=unlocked,
        unlock_cost=0 if unlocked else cost,
    )
    if unlocked:
        out.price_minor, out.currency = offer.price_minor, offer.currency
        out.quantity, out.unit = offer.quantity, offer.unit
        out.port_of_loading, out.payment_terms = offer.port_of_loading, list(offer.payment_terms)
    return out


async def list_offers(db: AsyncSession, user: User, rfq_id: uuid.UUID | None) -> list[OfferRead]:
    """The offers on the caller's own RFQ, newest first."""
    rfq = await rfqs.get_own(db, user, rfq_id)
    await _expire_offers(db, rfq.id)
    offers = list(await db.scalars(
        select(Offer).where(Offer.rfq_id == rfq.id, Offer.status != "withdrawn").order_by(Offer.published_at.desc())
    ))
    unlocked = set(await db.scalars(
        select(OfferUnlock.offer_id).where(OfferUnlock.buyer_business_id == user.business_id)
    ))
    sellers = await rfqs._businesses(db, [o.seller_business_id for o in offers])
    cost = await credits.price_of(db, "OFFER_UNLOCK")
    return [await _offer_out(db, o, o.id in unlocked, cost, sellers.get(o.seller_business_id)) for o in offers]


async def unlock_offer(db: AsyncSession, user: User, offer_id: uuid.UUID | None) -> OfferRead:
    """Pay OFFER_UNLOCK to see an offer's price and terms. Once per company:
    a second call, or a retry, costs nothing."""
    offer = None
    if offer_id is not None:
        offer = await db.scalar(select(Offer).where(Offer.id == offer_id, Offer.buyer_business_id == user.business_id))
    if offer is None or offer.status == "withdrawn":
        raise NotFound("Offer not found.")
    await _expire_offers(db, offer.rfq_id)
    await db.refresh(offer)
    already = await db.scalar(
        select(OfferUnlock.id).where(OfferUnlock.offer_id == offer.id, OfferUnlock.buyer_business_id == user.business_id)
    )
    if already is None:
        if offer.status != "published":
            raise Conflict("This offer has expired.")
        await credits.spend(
            db, user, "OFFER_UNLOCK", idempotency_key=unlock_key(offer.id, user.business_id),
            reference=("offer", str(offer.id)),
        )
        db.add(OfferUnlock(offer_id=offer.id, buyer_business_id=user.business_id, user_id=user.id, unlocked_at=utcnow()))
        try:
            await db.commit()
        except IntegrityError:  # a double click: the other request unlocked it
            await db.rollback()
        await db.refresh(offer)
    seller = await db.get(Business, offer.seller_business_id)
    return await _offer_out(db, offer, True, 0, seller)
