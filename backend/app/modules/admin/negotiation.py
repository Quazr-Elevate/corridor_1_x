"""/admin/chat/… and /admin/deals/{code}/chat — the desk's side of
negotiation (A-074, A-075): read both threads, write into either, release
or reject held messages, lift a suspension."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response
from sqlalchemy import select

from app.core.errors import NotFound
from app.core.security import parse_uuid
from app.models.business import Business
from app.models.deal import Deal
from app.models.negotiation import ChatMessage, CounterOffer
from app.modules.admin import service as audit
from app.modules.admin.deps import CanHandleSamples, CanLiftSuspension, CanTriageRfqs
from app.modules.admin.permissions import Perm
from app.modules.auth.deps import DbSession
from app import notifications
from app.models.negotiation import Sample, TermSheet
from app.modules.negotiation import counters, samples, service, term_sheets
from app.modules.negotiation.router import _mail_side, notify_new_message
from app.modules.negotiation.schemas import (
    CounterRelayIn,
    DeskChatOut,
    DeskCounterOut,
    DeskMessageIn,
    DeskMessageOut,
    DeskSampleOut,
    DeskTermSheetOut,
    TermSheetEditIn,
    DeskThreadOut,
    ForwardIn,
    HeldMessageOut,
    SampleHop,
    SealIn,
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


# ── Samples (CX-102) ─────────────────────────────────────────────────


async def _desk_samples(db, rows: list[tuple[Sample, Deal]]) -> list[DeskSampleOut]:
    hops = await samples.events(db, [s.id for s, _ in rows])
    return [
        DeskSampleOut(
            id=str(s.id), deal_code=d.code, status=s.status, seller_courier_ref=s.seller_courier_ref,
            retained_seal_no=s.retained_seal_no, forward_seal_no=s.forward_seal_no,
            forward_courier_ref=s.forward_courier_ref, verdict=s.verdict, review_note=s.review_note,
            hops=[SampleHop(status=e.to_status, at=e.created_at) for e in hops[s.id]], created_at=s.created_at,
        )
        for s, d in rows
    ]


@router.get("/samples", response_model=ItemList[DeskSampleOut], response_model_by_alias=True)
async def open_samples(_: CanHandleSamples, db: DbSession) -> ItemList[DeskSampleOut]:
    """Samples not yet reviewed, oldest first, with both legs."""
    return item_list(await _desk_samples(db, await samples.open_samples(db)))


@router.get("/deals/{code}/samples", response_model=ItemList[DeskSampleOut], response_model_by_alias=True)
async def deal_samples(code: str, _: CanHandleSamples, db: DbSession) -> ItemList[DeskSampleOut]:
    deal = await service.deal_by_code(db, code)
    rows = list(await db.scalars(select(Sample).where(Sample.deal_id == deal.id).order_by(Sample.created_at.desc())))
    return item_list(await _desk_samples(db, [(s, deal) for s in rows]))


async def _hop(db, admin, sample: Sample, deal: Deal, action: str, details: dict | None = None) -> DeskSampleOut:
    audit.record_action(db, admin=admin, action=f"sample.{action}", target_type="sample", target_id=sample.id,
                        details={"deal": deal.code, **(details or {})})
    await db.commit()
    return (await _desk_samples(db, [(sample, deal)]))[0]


@router.post("/samples/{sample_id}/at-hub", response_model=DeskSampleOut, response_model_by_alias=True)
async def sample_at_hub(sample_id: str, admin: CanHandleSamples, db: DbSession) -> DeskSampleOut:
    """The seller's parcel has arrived at the hub."""
    sample, deal = await samples.at_hub(db, admin.id, parse_uuid(sample_id))
    return await _hop(db, admin, sample, deal, "at_hub")


@router.post("/samples/{sample_id}/seal", response_model=DeskSampleOut, response_model_by_alias=True)
async def seal_sample(sample_id: str, payload: SealIn, admin: CanHandleSamples, db: DbSession) -> DeskSampleOut:
    """Split the sample and seal both halves; the hub keeps the retained half."""
    sample, deal = await samples.seal(db, admin.id, parse_uuid(sample_id), payload.retained_seal_no, payload.forward_seal_no)
    return await _hop(db, admin, sample, deal, "sealed",
                      {"retainedSealNo": sample.retained_seal_no, "forwardSealNo": sample.forward_seal_no})


@router.post("/samples/{sample_id}/forward", response_model=DeskSampleOut, response_model_by_alias=True)
async def forward_sample(
    sample_id: str, payload: ForwardIn, admin: CanHandleSamples, db: DbSession, background: BackgroundTasks
) -> DeskSampleOut:
    """Send the forward half to the buyer under Corridor One X's name. Refused
    until both halves are sealed."""
    sample, deal = await samples.forward(db, admin.id, parse_uuid(sample_id), payload.courier_ref)
    out = await _hop(db, admin, sample, deal, "forwarded")
    await _mail_side(background, db, deal, "buyer", notifications.send_sample_forwarded)
    return out


@router.post("/samples/{sample_id}/received", response_model=DeskSampleOut, response_model_by_alias=True)
async def sample_received(sample_id: str, admin: CanHandleSamples, db: DbSession) -> DeskSampleOut:
    """The courier confirms the buyer has the sample."""
    sample, deal = await samples.received(db, admin.id, parse_uuid(sample_id))
    return await _hop(db, admin, sample, deal, "received")


# ── Term sheets (CX-103) ─────────────────────────────────────────────


async def _desk_term_sheet(db, t: TermSheet, deal: Deal) -> DeskTermSheetOut:
    sheet = await counters.sheet_of(db, deal)
    return DeskTermSheetOut(
        id=str(t.id), deal_code=deal.code, version=t.version, status=t.status, product=t.product, quality=t.quality,
        packaging=t.packaging, quantity=t.quantity, unit=t.unit, incoterm=t.incoterm,
        port_of_loading=t.port_of_loading, destination_port=t.destination_port, delivery_from=t.delivery_from,
        delivery_to=t.delivery_to, buyer_price_minor=t.buyer_price_minor, buyer_currency=t.buyer_currency,
        buyer_payment_terms=t.buyer_payment_terms, seller_price_minor=t.seller_price_minor,
        seller_currency=t.seller_currency, seller_payment_terms=t.seller_payment_terms, margin_pct=t.margin_pct,
        min_margin_pct=sheet.min_margin_pct, max_margin_pct=sheet.max_margin_pct, notes=t.notes,
        content_sha256=t.content_sha256, buyer_accepted_at=t.buyer_accepted_at, seller_accepted_at=t.seller_accepted_at,
        declined_side=t.declined_side, decline_note=t.decline_note, withdraw_note=t.withdraw_note,
        issued_at=t.issued_at, agreed_at=t.agreed_at, superseded_at=t.superseded_at, created_at=t.created_at,
    )


@router.get("/deals/{code}/term-sheets", response_model=ItemList[DeskTermSheetOut], response_model_by_alias=True)
async def deal_term_sheets(code: str, _: CanTriageRfqs, db: DbSession) -> ItemList[DeskTermSheetOut]:
    """Every version of the deal's term sheet, newest first, with both prices and the margin."""
    deal = await service.deal_by_code(db, code)
    return item_list([await _desk_term_sheet(db, t, deal) for t in await term_sheets.of_deal(db, deal)])


@router.post(
    "/deals/{code}/term-sheets", response_model=DeskTermSheetOut, response_model_by_alias=True, status_code=201
)
async def draft_term_sheet(code: str, admin: CanTriageRfqs, db: DbSession) -> DeskTermSheetOut:
    """Start a new version: a copy of the last one, or for the first, the
    offer at the last accepted counter-offer's prices."""
    deal = await service.deal_by_code(db, code)
    t = await term_sheets.draft(db, admin.id, deal)
    audit.record_action(db, admin=admin, action="term_sheet.drafted", target_type="term_sheet", target_id=t.id,
                        details={"deal": deal.code, "version": t.version})
    await db.commit()
    return await _desk_term_sheet(db, t, deal)


@router.patch("/term-sheets/{sheet_id}", response_model=DeskTermSheetOut, response_model_by_alias=True)
async def edit_term_sheet(sheet_id: str, payload: TermSheetEditIn, _: CanTriageRfqs, db: DbSession) -> DeskTermSheetOut:
    """Change a draft. Issued versions are frozen."""
    t, deal = await term_sheets.edit(db, parse_uuid(sheet_id), payload.model_dump(exclude_unset=True))
    await db.commit()
    return await _desk_term_sheet(db, t, deal)


@router.post("/term-sheets/{sheet_id}/issue", response_model=DeskTermSheetOut, response_model_by_alias=True)
async def issue_term_sheet(
    sheet_id: str, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> DeskTermSheetOut:
    """Freeze the draft and send it to both sides to accept."""
    t, deal = await term_sheets.issue(
        db, admin.id, parse_uuid(sheet_id), may_approve_margin=Perm.margin_approve in admin.permissions
    )
    audit.record_action(db, admin=admin, action="term_sheet.issued", target_type="term_sheet", target_id=t.id,
                        details={"deal": deal.code, "version": t.version, "sha256": t.content_sha256,
                                 "marginPct": str(t.margin_pct)})
    await db.commit()
    for side in ("buyer", "seller"):
        await _mail_side(background, db, deal, side, notifications.send_term_sheet_issued)
    return await _desk_term_sheet(db, t, deal)


@router.post("/term-sheets/{sheet_id}/withdraw", response_model=DeskTermSheetOut, response_model_by_alias=True)
async def withdraw_term_sheet(
    sheet_id: str, payload: RejectMessageIn, admin: CanTriageRfqs, db: DbSession
) -> DeskTermSheetOut:
    """Take back a draft or an issued version that hasn't been agreed."""
    t, deal = await term_sheets.withdraw(db, parse_uuid(sheet_id), payload.reason)
    audit.record_action(db, admin=admin, action="term_sheet.withdrawn", target_type="term_sheet", target_id=t.id,
                        reason=payload.reason, details={"deal": deal.code, "version": t.version})
    await db.commit()
    return await _desk_term_sheet(db, t, deal)
