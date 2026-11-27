"""Term sheets (M4 · S8, CX-103, A-076, A-079).

    draft ─(desk issues)→ issued ─(both sides accept)→ agreed ─(a later version agreed)→ superseded
                            ├─(a side declines)→ declined
      draft, issued ─(desk)→ withdrawn

The desk drafts each version, starting from the last one or, for the first,
from the chosen offer, its quote and any accepted counter-offer. Issuing
hashes the terms; from then on they never change (a database trigger
refuses it). Each side accepts by sending back the hash it was shown, so
nobody agrees to a version they didn't read. Traders change terms only
through counter-offers. LOIs (S9) will point at an agreed version; a later
agreed version supersedes it and voids them."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.deal import Deal
from app.models.listing import SpecParameter
from app.models.negotiation import TERM_SHEET_OPEN, CounterOffer, TermSheet
from app.models.quote import CostSheet, Offer, Quote
from app.models.rfq import PAYMENT_TERMS, Rfq
from app.models.user import User
from app.modules.masking import service as masking
from app.modules.negotiation import counters
from app.modules.negotiation import service as chat
from app.shared import leakfilter

#: What the desk may set on a draft. Prices are per unit, in minor units.
EDITABLE = (
    "product", "quality", "packaging", "quantity", "incoterm", "port_of_loading", "destination_port",
    "delivery_from", "delivery_to", "buyer_price_minor", "buyer_payment_terms", "seller_price_minor",
    "seller_payment_terms", "notes",
)
REQUIRED = (
    "product", "quantity", "incoterm", "buyer_price_minor", "buyer_payment_terms", "seller_price_minor",
    "seller_payment_terms",
)
#: What the hash covers: every term, both prices, and which deal and version it is.
HASHED = (
    "product", "quality", "packaging", "quantity", "unit", "incoterm", "port_of_loading", "destination_port",
    "delivery_from", "delivery_to", "buyer_price_minor", "buyer_currency", "buyer_payment_terms",
    "seller_price_minor", "seller_currency", "seller_payment_terms", "notes",
)


def content_hash(sheet: TermSheet, deal_code: str) -> str:
    """SHA-256 of the terms as canonical JSON (sorted keys, no spaces)."""
    def plain(v: object) -> object:
        if isinstance(v, Decimal):
            return format(v.normalize(), "f")
        if isinstance(v, date):
            return v.isoformat()
        return v

    body = {"deal": deal_code, "version": sheet.version, **{f: plain(getattr(sheet, f)) for f in HASHED}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def margin_of(buyer_minor: int, seller_minor: int, sheet: CostSheet) -> Decimal:
    """The margin the two prices leave through the cost sheet, to 0.01 % (down)."""
    cost = Decimal(seller_minor + counters.other_costs(sheet)) * sheet.fx_rate * (1 + sheet.fx_buffer_pct / 100)
    return ((Decimal(buyer_minor) / cost - 1) * 100).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)


# ── The desk ─────────────────────────────────────────────────────────


async def of_deal(db: AsyncSession, deal: Deal) -> list[TermSheet]:
    """Every version, newest first."""
    return list(await db.scalars(
        select(TermSheet).where(TermSheet.deal_id == deal.id).order_by(TermSheet.version.desc())
    ))


async def _first_terms(db: AsyncSession, deal: Deal, sheet: CostSheet) -> dict:
    """Version 1: the chosen offer and its quote, at the prices of the last
    accepted counter-offer if there is one."""
    offer = await db.get(Offer, deal.chosen_offer_id)
    quote = await db.get(Quote, offer.quote_id)
    rfq = await db.get(Rfq, offer.rfq_id)
    buyer_price, seller_price = offer.price_minor, quote.price_minor
    accepted = await db.scalar(
        select(CounterOffer).where(CounterOffer.deal_id == deal.id, CounterOffer.status == "accepted")
        .order_by(CounterOffer.answered_at.desc()).limit(1)
    )
    if accepted is not None:
        if accepted.side == "buyer":
            buyer_price, seller_price = accepted.price_minor, accepted.implied_minor
        else:
            buyer_price, seller_price = accepted.implied_minor, accepted.price_minor
    params = {str(p.id): p for p in await db.scalars(select(SpecParameter).where(SpecParameter.category == rfq.category))}
    words = {"MIN": "at least", "MAX": "at most", "EQ": ""}
    specs = "; ".join(
        f"{params[s['parameter_id']].name}: {words.get(s['operator'], '')} {s['value']}"
        f"{' ' + params[s['parameter_id']].unit if params[s['parameter_id']].unit else ''}".replace("  ", " ")
        for s in (rfq.specs or []) if s["parameter_id"] in params
    )
    product = " ".join(x for x in (rfq.product_name, rfq.variety, rfq.grade) if x)
    quantity = accepted.quantity if accepted is not None and accepted.quantity else offer.quantity
    return dict(
        product=product[:200], quality=specs or None, packaging=rfq.packaging, quantity=quantity, unit=offer.unit,
        incoterm=offer.incoterm, port_of_loading=offer.port_of_loading, destination_port=rfq.destination_port,
        delivery_from=rfq.delivery_from, delivery_to=rfq.delivery_to,
        buyer_price_minor=buyer_price, buyer_currency=sheet.deal_currency,
        buyer_payment_terms=rfq.payment_terms or (offer.payment_terms or ["advance"])[0],
        seller_price_minor=seller_price, seller_currency=sheet.purchase_currency,
        seller_payment_terms=(quote.payment_terms or ["advance"])[0], notes=None,
    )


async def draft(db: AsyncSession, admin_id: uuid.UUID, deal: Deal) -> TermSheet:
    """A new draft, copied from the latest version or, for the first, built
    from the offer. One version is worked on at a time."""
    if deal.status not in chat.WRITABLE:
        raise Conflict("Term sheets are drafted while the deal is being negotiated.")
    if await db.scalar(select(TermSheet.id).where(TermSheet.deal_id == deal.id, TermSheet.status.in_(TERM_SHEET_OPEN))):
        raise Conflict("This deal already has a term sheet being drafted or waiting for answers.")
    sheet = await counters.sheet_of(db, deal)
    latest = await db.scalar(
        select(TermSheet).where(TermSheet.deal_id == deal.id).order_by(TermSheet.version.desc()).limit(1)
    )
    if latest is not None:
        terms = {f: getattr(latest, f) for f in (*EDITABLE, "unit", "buyer_currency", "seller_currency")}
    else:
        terms = await _first_terms(db, deal, sheet)
    version = (await db.scalar(select(func.max(TermSheet.version)).where(TermSheet.deal_id == deal.id)) or 0) + 1
    ts = TermSheet(
        id=uuid.uuid4(), deal_id=deal.id, version=version, status="draft", created_by=admin_id,
        margin_pct=margin_of(terms["buyer_price_minor"], terms["seller_price_minor"], sheet), created_at=utcnow(),
        **terms,
    )
    db.add(ts)
    return ts


async def desk_sheet(db: AsyncSession, sheet_id: uuid.UUID | None) -> tuple[TermSheet, Deal]:
    ts = await db.get(TermSheet, sheet_id) if sheet_id else None
    if ts is None:
        raise NotFound("Term sheet not found.")
    return ts, await db.get(Deal, ts.deal_id)


async def edit(db: AsyncSession, sheet_id: uuid.UUID | None, changes: dict) -> tuple[TermSheet, Deal]:
    """Change a draft. An issued version is frozen: draft a new one instead."""
    ts, deal = await desk_sheet(db, sheet_id)
    if ts.status != "draft":
        raise Conflict("An issued term sheet can't be changed. Draft a new version.")
    for field, value in changes.items():
        if field not in EDITABLE:
            raise BadRequest("That term can't be changed here.")
        if value is None and field in REQUIRED:
            raise BadRequest("Every term sheet needs a product, quantity, incoterm, both prices and payment terms.")
        if field.endswith("_payment_terms") and value not in PAYMENT_TERMS:
            raise BadRequest("Choose payment terms from the list.")
        if field == "quantity":
            value = Decimal(value).quantize(Decimal("0.01"))
        setattr(ts, field, value)
    if ts.delivery_from and ts.delivery_to and ts.delivery_to < ts.delivery_from:
        raise BadRequest("The delivery window must end on or after its start.")
    ts.margin_pct = margin_of(ts.buyer_price_minor, ts.seller_price_minor, await counters.sheet_of(db, deal))
    return ts, deal


async def issue(
    db: AsyncSession, admin_id: uuid.UUID, sheet_id: uuid.UUID | None, *, may_approve_margin: bool
) -> tuple[TermSheet, Deal]:
    """Freeze a draft and send it to both sides. A margin outside the cost
    sheet's floor and ceiling needs a desk manager, as for counter-offers."""
    ts, deal = await desk_sheet(db, sheet_id)
    if ts.status != "draft":
        raise Conflict("Only a draft can be issued.")
    if deal.status not in chat.WRITABLE:
        raise Conflict("Negotiation on this deal is closed.")
    sheet = await counters.sheet_of(db, deal)
    ts.margin_pct = margin_of(ts.buyer_price_minor, ts.seller_price_minor, sheet)
    if ts.margin_pct < 0:
        raise BadRequest("The buyer's price doesn't cover the seller's price and costs.")
    ceiling = sheet.max_margin_pct
    outside = ts.margin_pct < sheet.min_margin_pct or (ceiling is not None and ts.margin_pct > ceiling)
    if outside and not may_approve_margin:
        raise Forbidden(counters.MARGIN_LIMITS.format(floor=sheet.min_margin_pct, ceiling=ceiling))
    ts.content_sha256 = content_hash(ts, deal.code)
    ts.status, ts.issued_by, ts.issued_at = "issued", admin_id, utcnow()
    return ts, deal


async def withdraw(db: AsyncSession, sheet_id: uuid.UUID | None, note: str) -> tuple[TermSheet, Deal]:
    ts, deal = await desk_sheet(db, sheet_id)
    if ts.status not in TERM_SHEET_OPEN:
        raise Conflict("Only a draft or an issued term sheet can be withdrawn.")
    ts.status, ts.withdraw_note = "withdrawn", note
    return ts, deal


# ── Traders ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Answered:
    sheet: TermSheet
    deal: Deal
    side: str


async def visible_to(db: AsyncSession, user: User, code: str) -> tuple[str, Deal, list[TermSheet]]:
    """Every version this side has been shown (not drafts), newest first."""
    p = await chat.party(db, user, code)
    rows = [t for t in await of_deal(db, p.deal) if t.status != "draft" and t.content_sha256]
    return p.side, p.deal, rows


async def _issued(db: AsyncSession, user: User, code: str, version: int) -> tuple[TermSheet, Deal, str]:
    p = await chat.party(db, user, code)
    ts = await db.scalar(select(TermSheet).where(TermSheet.deal_id == p.deal.id, TermSheet.version == version))
    if ts is None or ts.status == "draft":
        raise NotFound("Term sheet not found.")
    if ts.status != "issued":
        raise Conflict("This term sheet is no longer open for answers.")
    if p.deal.status not in chat.WRITABLE:
        raise Conflict("Negotiation on this deal is closed.")
    chat.ensure_can_trade(user.business)
    return ts, p.deal, p.side


async def accept(db: AsyncSession, user: User, code: str, version: int, content_sha256: str) -> Answered:
    """Accept the exact version read (its hash). The second acceptance makes
    it agreed and supersedes the previous agreed version."""
    ts, deal, side = await _issued(db, user, code, version)
    if content_sha256 != ts.content_sha256:
        raise Conflict("This term sheet has changed since you opened it. Reload it and read it again.")
    if getattr(ts, f"{side}_accepted_at") is not None:
        return Answered(ts, deal, side)
    setattr(ts, f"{side}_accepted_at", utcnow())
    setattr(ts, f"{side}_accepted_by", user.id)
    if ts.buyer_accepted_at is None or ts.seller_accepted_at is None:
        return Answered(ts, deal, side)
    previous = await db.scalar(select(TermSheet).where(TermSheet.deal_id == deal.id, TermSheet.status == "agreed"))
    if previous is not None:
        previous.status, previous.superseded_at, previous.superseded_by_id = "superseded", utcnow(), ts.id
        # The partial unique index allows one agreed version; free it first.
        await db.flush()
    ts.status, ts.agreed_at = "agreed", utcnow()
    return Answered(ts, deal, side)


async def decline(db: AsyncSession, user: User, code: str, version: int, note: str) -> Answered:
    """Say no, with a reason the desk reads. The desk drafts a new version."""
    ts, deal, side = await _issued(db, user, code, version)
    result = leakfilter.check(note, await masking.legal_name_for_text_check(db, user.business_id))
    if result.verdict is not leakfilter.Verdict.PASS:
        raise BadRequest(f"Remove the {', '.join(result.reasons)} from the reason.")
    ts.status, ts.declined_side, ts.decline_note = "declined", side, note
    return Answered(ts, deal, side)
