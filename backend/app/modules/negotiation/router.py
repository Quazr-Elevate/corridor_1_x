"""/deals/{code}/… — a trader's side of a deal in negotiation (A-074)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app import notifications
from app.core.security import parse_uuid
from app.models.business import Business
from app.models.negotiation import ChatMessage, CounterOffer
from app.modules.accounts.service import owner_contact
from app.modules.auth.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.negotiation import Sample, SampleEvent
from app.modules.negotiation import counters, samples, service
from app.modules.negotiation.schemas import (
    ChatMessageOut,
    ChatOut,
    ChooseOfferIn,
    CounterAnswerIn,
    CounterIn,
    CounterOut,
    DispatchIn,
    MessageIn,
    NegotiationStarted,
    SampleHop,
    SampleOut,
    SampleReviewIn,
)
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.schemas import ItemList, item_list

router = APIRouter(prefix="/deals", tags=["deals"])

#: One "new message" email per thread an hour, however busy the chat.
_MAIL_EVERY = RateLimitRule("chat.mail:thread", limit=1, window_sec=60 * 60)


def message_out(m: ChatMessage) -> ChatMessageOut:
    author = {"own": "you", "relay": "counterparty", "desk": "corridor", "system": "system"}[m.origin]
    return ChatMessageOut(
        id=str(m.id), author=author, sender_code=m.sender_code if m.origin == "relay" else None, body=m.body,
        status=m.status, note=m.review_note if m.status == "rejected" else None, created_at=m.created_at,
    )


@router.post("/{code}/choose", response_model=NegotiationStarted, response_model_by_alias=True)
async def choose_offer(
    code: str, payload: ChooseOfferIn, user: CurrentUser, db: DbSession, background: BackgroundTasks
) -> NegotiationStarted:
    """Go ahead with one unlocked offer: negotiation opens with that seller;
    the other sellers are told their quote wasn't taken."""
    chosen = await service.choose_offer(db, user, code, parse_uuid(payload.offer_id))
    seller = await owner_contact(db, chosen.offer.seller_business_id)
    others = [await owner_contact(db, b) for b in chosen.others]
    await db.commit()
    category = chosen.rfq.category if chosen.rfq else "trade"
    if seller:
        background.add_task(
            notifications.deliver_safely, notifications.send_offer_chosen, to=seller.email,
            first_name=notifications.first_name_of(seller.full_name), category=category, deal_code=chosen.deal.code,
            rfq_id=str(chosen.offer.rfq_id),
        )
    for o in others:
        if o:
            background.add_task(
                notifications.deliver_safely, notifications.send_quote_not_taken, to=o.email,
                first_name=notifications.first_name_of(o.full_name), category=category,
            )
    return NegotiationStarted(
        deal_code=chosen.deal.code, deal_status=chosen.deal.status, chosen_offer_id=str(chosen.offer.id)
    )


async def _chat(db, user, code: str) -> ChatOut:
    p = await service.party(db, user, code)
    other_id = p.deal.seller_business_id if p.side == "buyer" else p.deal.buyer_business_id
    other = await db.get(Business, other_id) if other_id else None
    return ChatOut(
        deal_code=p.deal.code, deal_status=p.deal.status, side=p.side,
        counterparty_code=other.company_code if other else None,
        can_write=p.deal.status in service.WRITABLE and not user.business.is_suspended,
        suspended=user.business.is_suspended,
        messages=[message_out(m) for m in await service.thread_messages(db, p.thread.id)],
    )


@router.get("/{code}/chat", response_model=ChatOut, response_model_by_alias=True)
async def read_chat(code: str, user: CurrentUser, db: DbSession) -> ChatOut:
    """Your thread with Corridor One X on this deal."""
    return await _chat(db, user, code)


@router.post("/{code}/chat", response_model=ChatMessageOut, response_model_by_alias=True, status_code=201)
async def send_message(
    code: str, payload: MessageIn, user: CurrentUser, db: DbSession, background: BackgroundTasks
) -> ChatMessageOut:
    """Send a message. A clean one reaches the other side at once, by your
    company code; one that may reveal a company waits for Corridor One X; one
    with contact details is refused (400) and counts toward suspension."""
    sent = await service.send_message(db, user, code, payload.body)
    deal = (await service.party(db, user, code)).deal
    await db.commit()
    if sent.relay is not None:
        await notify_new_message(background, db, deal, sent.other_side)
    return message_out(sent.message)


async def notify_new_message(background: BackgroundTasks, db, deal, side: str) -> None:
    """Email the side that has a new message, at most once an hour per thread.
    The email has no text from the chat: that is read in the app."""
    business_id = deal.buyer_business_id if side == "buyer" else deal.seller_business_id
    key = f"{deal.id}:{side}"
    if not business_id or not (await get_limiter().hit(_MAIL_EVERY, key)).allowed:
        return
    contact = await owner_contact(db, business_id)
    if contact:
        background.add_task(
            notifications.deliver_safely, notifications.send_chat_message, to=contact.email,
            first_name=notifications.first_name_of(contact.full_name), deal_code=deal.code,
        )


# ── Counter-offers (CX-101) ──────────────────────────────────────────


def counter_out(c: CounterOffer, side: str) -> CounterOut:
    mine = c.side == side
    return CounterOut(
        id=str(c.id), mine=mine, price_minor=c.price_minor if mine else c.implied_minor,
        currency=c.currency if mine else c.implied_currency, quantity=c.quantity, note=c.note, status=c.status,
        decision_note=c.decision_note if mine else None, created_at=c.created_at,
    )


@router.get("/{code}/counters", response_model=ItemList[CounterOut], response_model_by_alias=True)
async def list_counters(code: str, user: CurrentUser, db: DbSession) -> ItemList[CounterOut]:
    """Your counter-offers, and the other side's that Corridor One X passed on,
    each in your own currency. Newest first."""
    side, rows = await counters.visible_to(db, user, code)
    return item_list([counter_out(c, side) for c in rows])


@router.post("/{code}/counters", response_model=CounterOut, response_model_by_alias=True, status_code=201)
async def propose_counter(code: str, payload: CounterIn, user: CurrentUser, db: DbSession) -> CounterOut:
    """Propose a new price. Corridor One X checks it before the other side sees it."""
    c = await counters.propose(db, user, code, payload.price_minor, payload.quantity, payload.note)
    await db.commit()
    return counter_out(c, c.side)


@router.post("/{code}/counters/{counter_id}/answer", response_model=CounterOut, response_model_by_alias=True)
async def answer_counter(
    code: str, counter_id: str, payload: CounterAnswerIn, user: CurrentUser, db: DbSession
) -> CounterOut:
    """Accept or decline the other side's counter-offer. An accepted one goes
    into the next term sheet (A-076)."""
    c = await counters.answer(db, user, code, parse_uuid(counter_id), payload.accept)
    await db.commit()
    return counter_out(c, "buyer" if c.side == "seller" else "seller")


# ── Samples (CX-102) ─────────────────────────────────────────────────

#: The hops each side sees. The buyer doesn't see the seller's leg (nor that
#: the hub split it); the seller doesn't see the forward leg's details.
_SEEN_BY = {
    "buyer": {"requested", "forwarded", "buyer_received", "reviewed"},
    "seller": {"requested", "seller_dispatched", "at_hub", "reviewed"},
}


def sample_out(s: Sample, side: str, hops: list[SampleEvent]) -> SampleOut:
    seller = side == "seller"
    return SampleOut(
        id=str(s.id),
        # The buyer sees "on its way to the hub" as plain "requested" until it is forwarded.
        status=s.status if seller or s.status in _SEEN_BY["buyer"] else "requested",
        hub_address=settings.sample_hub_address if seller and s.status == "requested" else None,
        courier_ref=s.seller_courier_ref if seller else None,
        forward_courier_ref=None if seller else s.forward_courier_ref,
        verdict=s.verdict, review_note=s.review_note,
        hops=[SampleHop(status=e.to_status, at=e.created_at) for e in hops if e.to_status in _SEEN_BY[side]],
        created_at=s.created_at,
    )


async def _mail_side(background: BackgroundTasks, db, deal, side: str, send) -> None:
    business_id = deal.buyer_business_id if side == "buyer" else deal.seller_business_id
    contact = await owner_contact(db, business_id) if business_id else None
    if contact:
        background.add_task(
            notifications.deliver_safely, send, to=contact.email,
            first_name=notifications.first_name_of(contact.full_name), deal_code=deal.code,
        )


@router.get("/{code}/samples", response_model=ItemList[SampleOut], response_model_by_alias=True)
async def list_samples(code: str, user: CurrentUser, db: DbSession) -> ItemList[SampleOut]:
    """This deal's samples, newest first, showing only your own leg."""
    side, _, rows = await samples.of_party(db, user, code)
    hops = await samples.events(db, [s.id for s in rows])
    return item_list([sample_out(s, side, hops[s.id]) for s in rows])


@router.post("/{code}/samples", response_model=SampleOut, response_model_by_alias=True, status_code=201)
async def request_sample(code: str, user: CurrentUser, db: DbSession, background: BackgroundTasks) -> SampleOut:
    """The buyer asks for a sample and pays the sample fee in credits (402
    when the balance is short). The seller is asked to send it to the hub."""
    sample = await samples.request(db, user, code)
    deal = (await service.party(db, user, code)).deal
    await db.commit()
    await _mail_side(background, db, deal, "seller", notifications.send_sample_requested)
    return sample_out(sample, "buyer", (await samples.events(db, [sample.id]))[sample.id])


@router.post("/{code}/samples/{sample_id}/dispatch", response_model=SampleOut, response_model_by_alias=True)
async def dispatch_sample(code: str, sample_id: str, payload: DispatchIn, user: CurrentUser, db: DbSession) -> SampleOut:
    """The seller has sent the sample to the hub, with the courier's tracking number."""
    sample = await samples.dispatch(db, user, code, parse_uuid(sample_id), payload.courier_ref)
    await db.commit()
    return sample_out(sample, "seller", (await samples.events(db, [sample.id]))[sample.id])


@router.post("/{code}/samples/{sample_id}/review", response_model=SampleOut, response_model_by_alias=True)
async def review_sample(
    code: str, sample_id: str, payload: SampleReviewIn, user: CurrentUser, db: DbSession, background: BackgroundTasks
) -> SampleOut:
    """The buyer records whether the sample passed."""
    sample = await samples.review(db, user, code, parse_uuid(sample_id), payload.verdict, payload.note)
    deal = (await service.party(db, user, code)).deal
    await db.commit()
    await _mail_side(background, db, deal, "seller", notifications.send_sample_reviewed)
    return sample_out(sample, "buyer", (await samples.events(db, [sample.id]))[sample.id])
