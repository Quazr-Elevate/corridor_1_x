"""/admin/chat/… and /admin/deals/{code}/chat — the desk's side of
negotiation (A-074, A-075): read both threads, write into either, release
or reject held messages, lift a suspension."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response

from app.core.errors import NotFound
from app.core.security import parse_uuid
from app.models.business import Business
from app.models.deal import Deal
from app.models.negotiation import ChatMessage, CounterOffer
from app.modules.admin import service as audit
from app.modules.admin.deps import CanLiftSuspension, CanTriageRfqs
from app.modules.admin.permissions import Perm
from app.modules.auth.deps import DbSession
from app.modules.negotiation import counters, service
from app.modules.negotiation.router import notify_new_message
from app.modules.negotiation.schemas import (
    CounterRelayIn,
    DeskChatOut,
    DeskCounterOut,
    DeskMessageIn,
    DeskMessageOut,
    DeskThreadOut,
    HeldMessageOut,
    LiftSuspensionIn,
    RejectMessageIn,
)
from app.shared.schemas import ItemList, item_list

router = APIRouter()


def _desk_message(m: ChatMessage) -> DeskMessageOut:
    return DeskMessageOut(
        id=str(m.id), origin=m.origin, sender_code=m.sender_code, body=m.body, status=m.status, flags=list(m.flags),
        note=m.review_note, created_at=m.created_at,
    )


async def _desk_chat(db, code: str) -> DeskChatOut:
    deal = await service.deal_by_code(db, code)
    threads = await service.threads_of(db, deal)
    out = []
    for side in ("buyer", "seller"):
        t = threads.get(side)
        if t is None:
            continue
        b = await db.get(Business, deal.buyer_business_id if side == "buyer" else deal.seller_business_id)
        out.append(DeskThreadOut(
            side=side, company_code=b.company_code if b else None, suspended=bool(b and b.is_suspended),
            messages=[_desk_message(m) for m in await service.thread_messages(db, t.id)],
        ))
    return DeskChatOut(deal_code=deal.code, deal_status=deal.status, threads=out)


@router.get("/deals/{code}/chat", response_model=DeskChatOut, response_model_by_alias=True)
async def read_deal_chat(code: str, _: CanTriageRfqs, db: DbSession) -> DeskChatOut:
    """Both threads of a deal, as each side sees them, with the filter's flags."""
    return await _desk_chat(db, code)


@router.post("/deals/{code}/chat/{side}", response_model=DeskChatOut, response_model_by_alias=True, status_code=201)
async def write_to_thread(
    code: str, side: str, payload: DeskMessageIn, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> DeskChatOut:
    """Write as Corridor One X into the buyer's or the seller's thread."""
    if side not in ("buyer", "seller"):
        raise NotFound("Thread not found.")
    deal = await service.deal_by_code(db, code)
    await service.desk_write(db, admin.id, deal, side, payload.body)
    audit.record_action(db, admin=admin, action="chat.desk_message", target_type="deal", target_id=deal.id,
                        details={"side": side})
    await db.commit()
    await notify_new_message(background, db, deal, side)
    return await _desk_chat(db, code)


@router.get("/chat/held", response_model=ItemList[HeldMessageOut], response_model_by_alias=True)
async def held_messages(_: CanTriageRfqs, db: DbSession) -> ItemList[HeldMessageOut]:
    """Messages the leak filter held for a person, oldest first."""
    return item_list([
        HeldMessageOut(
            id=str(m.id), deal_code=d.code, side=t.side, sender_code=m.sender_code, body=m.body, flags=list(m.flags),
            created_at=m.created_at,
        )
        for m, t, d in await service.held_messages(db)
    ])


@router.post("/chat/{message_id}/release", response_model=DeskMessageOut, response_model_by_alias=True)
async def release_message(
    message_id: str, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> DeskMessageOut:
    message, deal, to_side = await service.release(db, admin.id, parse_uuid(message_id))
    audit.record_action(db, admin=admin, action="chat.released", target_type="chat_message", target_id=message.id,
                        details={"deal": deal.code})
    await db.commit()
    await notify_new_message(background, db, deal, to_side)
    return _desk_message(message)


@router.post("/chat/{message_id}/reject", response_model=DeskMessageOut, response_model_by_alias=True)
async def reject_message(
    message_id: str, payload: RejectMessageIn, admin: CanTriageRfqs, db: DbSession
) -> DeskMessageOut:
    message, deal = await service.reject(db, admin.id, parse_uuid(message_id), payload.reason)
    audit.record_action(db, admin=admin, action="chat.rejected", target_type="chat_message", target_id=message.id,
                        reason=payload.reason, details={"deal": deal.code})
    await db.commit()
    return _desk_message(message)


@router.post("/businesses/{business_id}/lift-suspension", status_code=204, response_class=Response)
async def lift_suspension(business_id: str, payload: LiftSuspensionIn, admin: CanLiftSuspension, db: DbSession) -> Response:
    """A desk manager lets a suspended company trade again (A-075), with a reason."""
    business = await service.lift_suspension(db, parse_uuid(business_id))
    audit.record_action(db, admin=admin, action="business.suspension_lifted", target_type="business",
                        target_id=business.id, reason=payload.reason)
    await db.commit()
    return Response(status_code=204)


# ── Counter-offers (CX-101) ──────────────────────────────────────────


async def _desk_counter(db, c: CounterOffer, code: str) -> DeskCounterOut:
    deal = await db.get(Deal, c.deal_id)
    sheet = await counters.sheet_of(db, deal)
    return DeskCounterOut(
        id=str(c.id), deal_code=code, side=c.side, price_minor=c.price_minor, currency=c.currency,
        implied_minor=c.implied_minor, implied_currency=c.implied_currency, margin_pct=c.margin_pct,
        sheet_margin_pct=sheet.margin_pct, min_margin_pct=sheet.min_margin_pct, max_margin_pct=sheet.max_margin_pct,
        quantity=c.quantity, note=c.note, status=c.status, decision_note=c.decision_note, created_at=c.created_at,
    )


@router.get("/counters/pending", response_model=ItemList[DeskCounterOut], response_model_by_alias=True)
async def pending_counters(_: CanTriageRfqs, db: DbSession) -> ItemList[DeskCounterOut]:
    """Counter-offers waiting for the desk, oldest first, with what each means for the other side."""
    return item_list([await _desk_counter(db, c, d.code) for c, d in await counters.pending(db)])


@router.get("/deals/{code}/counters", response_model=ItemList[DeskCounterOut], response_model_by_alias=True)
async def deal_counters(code: str, _: CanTriageRfqs, db: DbSession) -> ItemList[DeskCounterOut]:
    deal = await service.deal_by_code(db, code)
    return item_list([await _desk_counter(db, c, deal.code) for c in await counters.of_deal(db, deal)])


@router.post("/counters/{counter_id}/relay", response_model=DeskCounterOut, response_model_by_alias=True)
async def relay_counter(
    counter_id: str, payload: CounterRelayIn, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> DeskCounterOut:
    """Pass a counter-offer on, at the sheet's margin or another (outside the
    floor and ceiling only a desk manager may)."""
    d = await counters.relay(
        db, admin.id, parse_uuid(counter_id), payload.margin_pct,
        may_approve_margin=Perm.margin_approve in admin.permissions,
    )
    audit.record_action(db, admin=admin, action="counter.relayed", target_type="counter_offer", target_id=d.counter.id,
                        details={"deal": d.deal.code, "marginPct": str(d.counter.margin_pct)})
    await db.commit()
    await notify_new_message(background, db, d.deal, "seller" if d.counter.side == "buyer" else "buyer")
    return await _desk_counter(db, d.counter, d.deal.code)


@router.post("/counters/{counter_id}/reject", response_model=DeskCounterOut, response_model_by_alias=True)
async def reject_counter(counter_id: str, payload: RejectMessageIn, admin: CanTriageRfqs, db: DbSession) -> DeskCounterOut:
    """Refuse a counter-offer; the side that made it sees the reason."""
    d = await counters.reject(db, admin.id, parse_uuid(counter_id), payload.reason)
    audit.record_action(db, admin=admin, action="counter.rejected", target_type="counter_offer", target_id=d.counter.id,
                        reason=payload.reason, details={"deal": d.deal.code})
    await db.commit()
    return await _desk_counter(db, d.counter, d.deal.code)
