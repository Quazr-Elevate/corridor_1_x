"""Negotiation (M4 · S8, CX-099, A-074, A-075).

* The buyer chooses one unlocked offer: the deal moves QUOTED → NEGOTIATING,
  its seller is fixed, the other offers close as ``not_chosen``, and the two
  chat threads open.
* Each side writes only in its own thread. The leak filter reads every
  message first: PASS is delivered and copied into the other thread with
  the sender's company code; REVIEW waits for the desk; BLOCKED is refused
  with the reason and recorded as a strike. Three strikes in 90 days suspend
  the company until a desk manager lifts it.
* The desk reads both threads, writes into either, and releases or rejects
  held messages.

The other side is only ever named by company code; nothing here reads the
identity vault except the sender's own name, to look for it in their own
text."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.business import Business
from app.models.deal import Deal, DealStatus
from app.models.negotiation import MAX_MESSAGE, ChatMessage, ChatThread, LeakStrike
from app.models.quote import Offer, OfferUnlock
from app.models.rfq import Rfq
from app.models.user import User
from app.modules.deals.machine import Actor, transition
from app.modules.masking import service as masking
from app.ratelimit import RateLimitRule, get_limiter
from app.shared import leakfilter

log = logging.getLogger(__name__)

#: Messages one person may send in ten minutes.
SEND = RateLimitRule("chat.send:user", limit=30, window_sec=10 * 60)
#: A-075: this many blocked messages in the window suspend the company.
STRIKE_LIMIT = 3
STRIKE_WINDOW = timedelta(days=90)
SUSPENDED = "Your company can't trade on Corridor One X right now: three messages were blocked for contact details. Contact support."

#: Chat is open while the deal is being negotiated; it can be read later.
WRITABLE = (DealStatus.NEGOTIATING,)
READABLE = (
    DealStatus.NEGOTIATING, DealStatus.LOI_SIGNED, DealStatus.CONTRACTED, DealStatus.ADVANCE_PAID,
    DealStatus.IN_PRODUCTION, DealStatus.INSPECTED, DealStatus.SHIPPED, DealStatus.ARRIVED, DealStatus.DELIVERED,
    DealStatus.ACCEPTED, DealStatus.SETTLED, DealStatus.CLOSED, DealStatus.DISPUTED, DealStatus.CANCELLED,
)


def ensure_can_trade(business: Business) -> None:
    """Refuse a write by a suspended company (A-075); reading stays open."""
    if business.is_suspended:
        raise Forbidden(SUSPENDED)


# ── Choosing an offer ────────────────────────────────────────────────


@dataclass(frozen=True)
class Chosen:
    deal: Deal
    offer: Offer
    rfq: Rfq
    #: Sellers whose offers closed as not chosen.
    others: list[uuid.UUID]


async def choose_offer(db: AsyncSession, user: User, code: str, offer_id: uuid.UUID | None) -> Chosen:
    """The buyer goes ahead with one offer it has unlocked. Everything happens
    in the caller's transaction, which commits."""
    deal = await db.scalar(
        select(Deal).where(Deal.code == code.strip().upper(), Deal.buyer_business_id == user.business_id)
    )
    if deal is None:
        raise NotFound("Deal not found.")
    ensure_can_trade(user.business)
    offer = await db.scalar(select(Offer).where(Offer.id == offer_id, Offer.deal_id == deal.id)) if offer_id else None
    if offer is None:
        raise NotFound("Offer not found.")
    if deal.status != DealStatus.QUOTED:
        raise Conflict("An offer has already been chosen on this deal." if deal.chosen_offer_id else
                       "This deal isn't taking offers.")
    if offer.status != "published" or offer.valid_until < utcnow().date():
        raise Conflict("This offer is no longer open.")
    unlocked = await db.scalar(
        select(OfferUnlock.id).where(OfferUnlock.offer_id == offer.id, OfferUnlock.buyer_business_id == user.business_id)
    )
    if unlocked is None:
        raise BadRequest("Open the offer's price before you choose it.")

    others = list(await db.scalars(
        select(Offer.seller_business_id).where(
            Offer.deal_id == deal.id, Offer.id != offer.id, Offer.status == "published"
        )
    ))
    await db.execute(
        update(Offer).where(Offer.deal_id == deal.id, Offer.id != offer.id, Offer.status == "published")
        .values(status="not_chosen").execution_options(synchronize_session=False)
    )
    deal.seller_business_id = offer.seller_business_id
    deal.chosen_offer_id = offer.id
    transition(db, deal, DealStatus.NEGOTIATING, actor=Actor.user(user.id), details={"offer": str(offer.id)})
    threads = [ChatThread(id=uuid.uuid4(), deal_id=deal.id, side=side) for side in ("buyer", "seller")]
    db.add_all(threads)
    await db.flush()  # the opening lines need their threads in place
    for thread in threads:
        db.add(ChatMessage(
            thread_id=thread.id, origin="system", status="delivered", flags=[], created_at=utcnow(),
            body=(
                "Negotiation is open. You are talking to Corridor One X; the other side sees only your company "
                "code. Messages with phone numbers, emails, links or company names are refused."
            ),
        ))
    rfq = await db.get(Rfq, offer.rfq_id)
    return Chosen(deal=deal, offer=offer, rfq=rfq, others=others)


# ── The trader's thread ──────────────────────────────────────────────


@dataclass(frozen=True)
class Party:
    deal: Deal
    side: str
    thread: ChatThread


async def party(db: AsyncSession, user: User, code: str) -> Party:
    """The caller's side of a deal in negotiation or later; anyone else gets 404."""
    deal = await db.scalar(select(Deal).where(Deal.code == code.strip().upper()))
    if deal is None or deal.status not in READABLE:
        raise NotFound("Deal not found.")
    if deal.buyer_business_id == user.business_id:
        side = "buyer"
    elif deal.seller_business_id == user.business_id:
        side = "seller"
    else:
        raise NotFound("Deal not found.")
    thread = await db.scalar(select(ChatThread).where(ChatThread.deal_id == deal.id, ChatThread.side == side))
    if thread is None:
        raise NotFound("Deal not found.")
    return Party(deal=deal, side=side, thread=thread)


async def thread_messages(db: AsyncSession, thread_id: uuid.UUID) -> list[ChatMessage]:
    return list(await db.scalars(
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at, ChatMessage.id)
    ))


@dataclass(frozen=True)
class Sent:
    message: ChatMessage
    #: The copy in the other thread when the message went straight through.
    relay: ChatMessage | None
    other_side: str


async def send_message(db: AsyncSession, user: User, code: str, body: str) -> Sent:
    """Write in the caller's thread. The caller commits; a blocked message is
    committed here, with its strike, before the refusal is raised."""
    p = await party(db, user, code)
    if p.deal.status not in WRITABLE:
        raise Conflict("This conversation is closed.")
    ensure_can_trade(user.business)
    text = " ".join(body.split()) if "\n" not in body else body.strip()
    if not text:
        raise BadRequest("Write a message first.")
    if len(text) > MAX_MESSAGE:
        raise BadRequest(f"Keep messages under {MAX_MESSAGE} characters.")
    await get_limiter().check(SEND, str(user.id))

    result = leakfilter.check(text, await masking.legal_name_for_text_check(db, user.business_id))
    if result.verdict is leakfilter.Verdict.BLOCKED:
        await _strike(db, user, p.deal, list(result.reasons))
        await db.commit()
        raise BadRequest(
            f"Not sent: remove the {', '.join(result.reasons)}. Corridor One X carries every contact between the two sides."
        )
    held = result.verdict is leakfilter.Verdict.REVIEW
    message = ChatMessage(
        id=uuid.uuid4(), thread_id=p.thread.id, origin="own", body=text, status="held" if held else "delivered",
        author_user_id=user.id, author_business_id=user.business_id, sender_code=user.business.company_code,
        flags=list(result.reasons), created_at=utcnow(),
    )
    db.add(message)
    relay = None if held else await _relay(db, p.deal, p.side, message)
    return Sent(message=message, relay=relay, other_side=_other(p.side))


def _other(side: str) -> str:
    return "seller" if side == "buyer" else "buyer"


async def _relay(db: AsyncSession, deal: Deal, from_side: str, message: ChatMessage) -> ChatMessage:
    """Copy a cleared message into the other side's thread."""
    other = await db.scalar(
        select(ChatThread).where(ChatThread.deal_id == deal.id, ChatThread.side == _other(from_side))
    )
    copy = ChatMessage(
        id=uuid.uuid4(), thread_id=other.id, origin="relay", body=message.body, status="delivered",
        sender_code=message.sender_code, relayed_from_id=message.id, flags=[], created_at=utcnow(),
    )
    db.add(copy)
    return copy


async def _strike(db: AsyncSession, user: User, deal: Deal, reasons: list[str]) -> None:
    db.add(LeakStrike(business_id=user.business_id, user_id=user.id, deal_id=deal.id, reasons=reasons,
                      created_at=utcnow()))
    await db.flush()
    since = utcnow() - STRIKE_WINDOW
    count = await db.scalar(
        select(func.count(LeakStrike.id)).where(LeakStrike.business_id == user.business_id, LeakStrike.created_at >= since)
    )
    business = await db.get(Business, user.business_id)
    if count >= STRIKE_LIMIT and not business.is_suspended:
        business.suspended_at = utcnow()
        business.suspended_reason = f"{STRIKE_LIMIT} chat messages blocked for contact details within 90 days"
        log.warning("business_suspended business=%s strikes=%s", business.id, count)


# ── The desk ─────────────────────────────────────────────────────────


async def deal_by_code(db: AsyncSession, code: str) -> Deal:
    deal = await db.scalar(select(Deal).where(Deal.code == code.strip().upper()))
    if deal is None or deal.status not in READABLE:
        raise NotFound("Deal not found.")
    return deal


async def threads_of(db: AsyncSession, deal: Deal) -> dict[str, ChatThread]:
    return {t.side: t for t in await db.scalars(select(ChatThread).where(ChatThread.deal_id == deal.id))}


async def desk_write(db: AsyncSession, admin_id: uuid.UUID, deal: Deal, side: str, body: str) -> ChatMessage:
    if deal.status not in WRITABLE:
        raise Conflict("This conversation is closed.")
    text = body.strip()
    if not text:
        raise BadRequest("Write a message first.")
    thread = (await threads_of(db, deal)).get(side)
    if thread is None:
        raise NotFound("Thread not found.")
    message = ChatMessage(
        id=uuid.uuid4(), thread_id=thread.id, origin="desk", body=text[:MAX_MESSAGE], status="delivered",
        admin_id=admin_id, flags=[], created_at=utcnow(),
    )
    db.add(message)
    return message


async def held_messages(db: AsyncSession) -> list[tuple[ChatMessage, ChatThread, Deal]]:
    """Messages waiting for the desk, oldest first."""
    return list((await db.execute(
        select(ChatMessage, ChatThread, Deal)
        .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
        .join(Deal, Deal.id == ChatThread.deal_id)
        .where(ChatMessage.status == "held")
        .order_by(ChatMessage.created_at)
    )).all())


async def _held(db: AsyncSession, message_id: uuid.UUID | None) -> tuple[ChatMessage, ChatThread, Deal]:
    message = await db.get(ChatMessage, message_id) if message_id else None
    if message is None:
        raise NotFound("Message not found.")
    if message.status != "held":
        raise Conflict("This message has already been decided.")
    thread = await db.get(ChatThread, message.thread_id)
    return message, thread, await db.get(Deal, thread.deal_id)


async def release(db: AsyncSession, admin_id: uuid.UUID, message_id: uuid.UUID | None) -> tuple[ChatMessage, Deal, str]:
    """The desk lets a held message through: it is copied to the other side."""
    message, thread, deal = await _held(db, message_id)
    if deal.status not in WRITABLE:
        raise Conflict("This conversation is closed.")
    message.status = "delivered"
    message.admin_id = admin_id
    message.reviewed_at = utcnow()
    await _relay(db, deal, thread.side, message)
    return message, deal, _other(thread.side)


async def reject(db: AsyncSession, admin_id: uuid.UUID, message_id: uuid.UUID | None, note: str) -> tuple[ChatMessage, Deal]:
    """The desk stops a held message; the sender sees why."""
    message, _, deal = await _held(db, message_id)
    message.status = "rejected"
    message.admin_id = admin_id
    message.reviewed_at = utcnow()
    message.review_note = note
    return message, deal


async def lift_suspension(db: AsyncSession, business_id: uuid.UUID | None) -> Business:
    business = await db.get(Business, business_id) if business_id else None
    if business is None:
        raise NotFound("Business not found.")
    if not business.is_suspended:
        raise Conflict("This company isn't suspended.")
    business.suspended_at = None
    business.suspended_reason = None
    return business
