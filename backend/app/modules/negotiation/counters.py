"""Counter-offers (M4 · S8, CX-101, A-078).

A side proposes a new price in its own currency. The desk sees what it
means for the other side, back-solved through the deal's cost sheet: from
the buyer's price, the seller price that keeps the sheet's costs and
margin; from the seller's price, the selling price the sheet would give.
The desk passes it on (at the sheet's margin or another one), or refuses it
with a reason. The other side then accepts or declines. Neither side ever
sees the other's own price, the margin or the formula.

Rounding always favours Corridor One X: an implied seller price rounds
down, an implied buyer price rounds up."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.deal import Deal
from app.models.negotiation import COUNTER_OPEN, CounterOffer
from app.models.quote import COST_LINES, CostSheet, Offer
from app.models.user import User
from app.modules.masking import service as masking
from app.modules.negotiation import service as chat
from app.ratelimit import RateLimitRule, get_limiter
from app.shared import leakfilter

#: Counter-offers one side may make on one deal in a day.
PER_DAY = RateLimitRule("counter.create:deal_side", limit=10, window_sec=24 * 60 * 60)
MARGIN_LIMITS = "A margin under {floor}% or over {ceiling}% needs a desk manager."


def _others(sheet: CostSheet) -> int:
    """The sheet's costs on top of the purchase price, per unit."""
    return sum(getattr(sheet, f"{line}_minor") for line in COST_LINES)


def _factor(sheet: CostSheet, margin_pct: Decimal) -> Decimal:
    return sheet.fx_rate * (1 + sheet.fx_buffer_pct / 100) * (1 + margin_pct / 100)


def seller_price_for(buyer_minor: int, sheet: CostSheet, margin_pct: Decimal) -> int:
    """The seller price a buyer price allows, per unit, in the seller's currency."""
    total = (Decimal(buyer_minor) / _factor(sheet, margin_pct)).to_integral_value(rounding=ROUND_FLOOR)
    return int(total) - _others(sheet)


def buyer_price_for(seller_minor: int, sheet: CostSheet, margin_pct: Decimal) -> int:
    """The selling price a seller price gives, per unit, in the deal currency."""
    total = Decimal(seller_minor + _others(sheet))
    return int((total * _factor(sheet, margin_pct)).to_integral_value(rounding=ROUND_CEILING))


def _implied(side: str, price_minor: int, sheet: CostSheet, margin_pct: Decimal) -> tuple[int, str]:
    if side == "buyer":
        implied = seller_price_for(price_minor, sheet, margin_pct)
        if implied <= 0:
            raise BadRequest("That price doesn't cover freight and costs. Offer a higher price.")
        return implied, sheet.purchase_currency
    return buyer_price_for(price_minor, sheet, margin_pct), sheet.deal_currency


async def sheet_of(db: AsyncSession, deal: Deal) -> CostSheet:
    offer = await db.get(Offer, deal.chosen_offer_id) if deal.chosen_offer_id else None
    sheet = await db.get(CostSheet, offer.cost_sheet_id) if offer else None
    if sheet is None:
        raise Conflict("This deal has no priced offer to counter.")
    return sheet


# ── Traders ──────────────────────────────────────────────────────────


async def propose(
    db: AsyncSession, user: User, code: str, price_minor: int, quantity: Decimal | None, note: str | None
) -> CounterOffer:
    """A side's counter-offer, waiting for the desk. A newer one replaces the
    same side's open one. The note passes the leak filter like a message."""
    p = await chat.party(db, user, code)
    if p.deal.status not in chat.WRITABLE:
        raise Conflict("Negotiation on this deal is closed.")
    chat.ensure_can_trade(user.business)
    if note:
        result = leakfilter.check(note, await masking.legal_name_for_text_check(db, user.business_id))
        if result.verdict is not leakfilter.Verdict.PASS:
            raise BadRequest(f"Remove the {', '.join(result.reasons)} from the note. Use the chat for anything else.")
    await get_limiter().check(PER_DAY, f"{p.deal.id}:{p.side}")
    sheet = await sheet_of(db, p.deal)
    implied, implied_currency = _implied(p.side, price_minor, sheet, sheet.margin_pct)
    await db.execute(
        update(CounterOffer)
        .where(CounterOffer.deal_id == p.deal.id, CounterOffer.side == p.side, CounterOffer.status.in_(COUNTER_OPEN))
        .values(status="superseded").execution_options(synchronize_session=False)
    )
    counter = CounterOffer(
        id=uuid.uuid4(), deal_id=p.deal.id, side=p.side, price_minor=price_minor,
        currency=sheet.deal_currency if p.side == "buyer" else sheet.purchase_currency,
        quantity=quantity, note=note or None, implied_minor=implied, implied_currency=implied_currency,
        margin_pct=sheet.margin_pct, status="pending_desk", created_by_user_id=user.id, created_at=utcnow(),
    )
    db.add(counter)
    return counter


async def visible_to(db: AsyncSession, user: User, code: str) -> tuple[str, list[CounterOffer]]:
    """This side's own counters, and the other side's ones the desk passed on."""
    p = await chat.party(db, user, code)
    rows = list(await db.scalars(
        select(CounterOffer).where(CounterOffer.deal_id == p.deal.id).order_by(CounterOffer.created_at.desc())
    ))
    passed_on = ("relayed", "accepted", "declined")
    return p.side, [c for c in rows if c.side == p.side or c.status in passed_on]


async def answer(db: AsyncSession, user: User, code: str, counter_id: uuid.UUID | None, accept: bool) -> CounterOffer:
    """The other side accepts or declines a counter the desk passed on."""
    p = await chat.party(db, user, code)
    if p.deal.status not in chat.WRITABLE:
        raise Conflict("Negotiation on this deal is closed.")
    chat.ensure_can_trade(user.business)
    counter = await db.get(CounterOffer, counter_id) if counter_id else None
    if counter is None or counter.deal_id != p.deal.id or counter.side == p.side:
        raise NotFound("Counter-offer not found.")
    if counter.status != "relayed":
        raise Conflict("This counter-offer has already been answered or replaced.")
    counter.status = "accepted" if accept else "declined"
    counter.answered_at = utcnow()
    return counter


# ── The desk ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Decided:
    counter: CounterOffer
    deal: Deal


async def _pending(db: AsyncSession, counter_id: uuid.UUID | None) -> tuple[CounterOffer, Deal]:
    counter = await db.get(CounterOffer, counter_id) if counter_id else None
    if counter is None:
        raise NotFound("Counter-offer not found.")
    if counter.status != "pending_desk":
        raise Conflict("This counter-offer has already been decided.")
    deal = await db.get(Deal, counter.deal_id)
    if deal.status not in chat.WRITABLE:
        raise Conflict("Negotiation on this deal is closed.")
    return counter, deal


async def relay(
    db: AsyncSession, admin_id: uuid.UUID, counter_id: uuid.UUID | None, margin_pct: Decimal | None, *,
    may_approve_margin: bool,
) -> Decided:
    """Pass a counter on, at the sheet's margin or another. A margin outside
    the sheet's floor and ceiling needs a desk manager, as on cost sheets."""
    counter, deal = await _pending(db, counter_id)
    sheet = await sheet_of(db, deal)
    if margin_pct is not None:
        margin_pct = margin_pct.quantize(Decimal("0.01"))
    if margin_pct is not None and margin_pct != counter.margin_pct:
        ceiling = sheet.max_margin_pct
        outside = margin_pct < sheet.min_margin_pct or (ceiling is not None and margin_pct > ceiling)
        if outside and not may_approve_margin:
            raise Forbidden(MARGIN_LIMITS.format(floor=sheet.min_margin_pct, ceiling=ceiling))
        counter.implied_minor, counter.implied_currency = _implied(counter.side, counter.price_minor, sheet, margin_pct)
        counter.margin_pct = margin_pct
    counter.status = "relayed"
    counter.decided_by = admin_id
    counter.decided_at = utcnow()
    return Decided(counter, deal)


async def reject(db: AsyncSession, admin_id: uuid.UUID, counter_id: uuid.UUID | None, note: str) -> Decided:
    counter, deal = await _pending(db, counter_id)
    counter.status = "rejected"
    counter.decided_by = admin_id
    counter.decided_at = utcnow()
    counter.decision_note = note
    return Decided(counter, deal)


async def pending(db: AsyncSession) -> list[tuple[CounterOffer, Deal]]:
    return list((await db.execute(
        select(CounterOffer, Deal).join(Deal, Deal.id == CounterOffer.deal_id)
        .where(CounterOffer.status == "pending_desk").order_by(CounterOffer.created_at)
    )).all())


async def of_deal(db: AsyncSession, deal: Deal) -> list[CounterOffer]:
    return list(await db.scalars(
        select(CounterOffer).where(CounterOffer.deal_id == deal.id).order_by(CounterOffer.created_at.desc())
    ))
