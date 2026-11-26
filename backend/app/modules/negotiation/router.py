"""/deals/{code}/… — a trader's side of a deal in negotiation (A-074)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app import notifications
from app.core.security import parse_uuid
from app.models.business import Business
from app.models.negotiation import ChatMessage
from app.modules.accounts.service import owner_contact
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.negotiation import service
from app.modules.negotiation.schemas import ChatMessageOut, ChatOut, ChooseOfferIn, MessageIn, NegotiationStarted
from app.ratelimit import RateLimitRule, get_limiter

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
