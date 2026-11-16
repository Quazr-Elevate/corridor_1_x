"""/admin/rfqs/* — the trade desk's triage queue (build plan 20.1) — and the
desk's settings. Parties appear as company codes. Every decision is in the
audit trail and on the deal's own event log."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app import notifications
from app.core.security import parse_uuid
from app.models.rfq import RfqStatus
from app.modules.accounts.service import get_owner
from app.modules.admin import service as audit
from app.modules.admin.deps import CanConfigureTrade, CanTriageRfqs
from app.modules.auth.deps import DbSession
from app.modules.rfq import service
from app.modules.rfq.schemas import (
    DeskReasonIn,
    DeskRfqDetail,
    DeskRfqList,
    DeskStatus,
    HeldCountryIn,
    HeldCountryOut,
    MatchAdd,
    TradeSettingIn,
    TradeSettingOut,
)
from app.shared.schemas import ItemList, item_list

router = APIRouter()


def _status(rfq, deal_status: str | None) -> DeskStatus:
    return DeskStatus(id=str(rfq.id), status=rfq.status, deal_status=deal_status)


@router.get("/rfqs", response_model=DeskRfqList, response_model_by_alias=True)
async def list_rfqs(
    _: CanTriageRfqs,
    db: DbSession,
    queue: Literal["pending", "all"] = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> DeskRfqList:
    total, rows = await service.desk_list(db, queue=queue, limit=limit, offset=offset)
    return DeskRfqList(total=total, items=rows)


@router.get("/rfqs/{rfq_id}", response_model=DeskRfqDetail, response_model_by_alias=True)
async def rfq_detail(rfq_id: str, _: CanTriageRfqs, db: DbSession) -> DeskRfqDetail:
    return await service.desk_detail(db, parse_uuid(rfq_id))


@router.post("/rfqs/{rfq_id}/rematch", response_model=DeskRfqDetail, response_model_by_alias=True)
async def rematch(rfq_id: str, admin: CanTriageRfqs, db: DbSession) -> DeskRfqDetail:
    rfq = await service.desk_rematch(db, parse_uuid(rfq_id))
    audit.record_action(db, admin=admin, action="rfq.rematch", target_type="rfq", target_id=rfq.id)
    await db.commit()
    return await service.desk_detail(db, rfq.id)


@router.post("/rfqs/{rfq_id}/matches", response_model=DeskRfqDetail, response_model_by_alias=True, status_code=201)
async def add_match(rfq_id: str, payload: MatchAdd, admin: CanTriageRfqs, db: DbSession) -> DeskRfqDetail:
    match = await service.desk_add_match(db, parse_uuid(rfq_id), payload.listing_id)
    audit.record_action(
        db, admin=admin, action="rfq.match_add", target_type="rfq", target_id=match.rfq_id,
        details={"match_id": str(match.id), "listing_id": str(match.listing_id)},
    )
    await db.commit()
    return await service.desk_detail(db, match.rfq_id)


@router.delete("/rfqs/{rfq_id}/matches/{match_id}", status_code=204, response_class=Response)
async def remove_match(rfq_id: str, match_id: str, admin: CanTriageRfqs, db: DbSession) -> Response:
    match = await service.desk_remove_match(db, parse_uuid(rfq_id), parse_uuid(match_id))
    audit.record_action(
        db, admin=admin, action="rfq.match_remove", target_type="rfq", target_id=match.rfq_id,
        details={"match_id": str(match.id)},
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/rfqs/{rfq_id}/confirm", response_model=DeskStatus, response_model_by_alias=True)
async def confirm_matches(
    rfq_id: str, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> DeskStatus:
    """Confirm the proposed sellers. Only now are they told."""
    rfq, sellers = await service.desk_confirm(db, admin.id, parse_uuid(rfq_id))
    audit.record_action(
        db, admin=admin, action="rfq.confirm", target_type="rfq", target_id=rfq.id, details={"sellers": len(sellers)}
    )
    owners = [await get_owner(db, seller) for seller in sellers]
    await db.commit()
    for owner in owners:
        if owner is not None:
            background.add_task(
                notifications.deliver_safely, notifications.send_rfq_matched, to=owner.email,
                first_name=notifications.first_name_of(owner.full_name), category=rfq.category,
            )
    return _status(rfq, await service.deal_status_of(db, rfq))


@router.post("/rfqs/{rfq_id}/reject", response_model=DeskStatus, response_model_by_alias=True)
async def reject_rfq(rfq_id: str, payload: DeskReasonIn, admin: CanTriageRfqs, db: DbSession) -> DeskStatus:
    """Refuse an RFQ. The buyer sees the reason and is refunded."""
    reason = payload.reason
    rfq, deal = await service.desk_close(db, admin.id, parse_uuid(rfq_id), to=RfqStatus.rejected, reason=reason)
    audit.record_action(db, admin=admin, action="rfq.reject", target_type="rfq", target_id=rfq.id, reason=reason)
    await db.commit()
    return _status(rfq, deal.status)


@router.post("/rfqs/{rfq_id}/no-match", response_model=DeskStatus, response_model_by_alias=True)
async def close_unmatched(rfq_id: str, admin: CanTriageRfqs, db: DbSession) -> DeskStatus:
    """Close an RFQ no seller fits. The buyer is refunded."""
    rfq, deal = await service.desk_close(db, admin.id, parse_uuid(rfq_id), to=RfqStatus.unmatched, reason="")
    audit.record_action(db, admin=admin, action="rfq.no_match", target_type="rfq", target_id=rfq.id)
    await db.commit()
    return _status(rfq, deal.status)


@router.post("/rfqs/{rfq_id}/hold", response_model=DeskStatus, response_model_by_alias=True)
async def hold_rfq(rfq_id: str, payload: DeskReasonIn, admin: CanTriageRfqs, db: DbSession) -> DeskStatus:
    reason = payload.reason
    rfq = await service.desk_hold(db, parse_uuid(rfq_id), reason)
    audit.record_action(db, admin=admin, action="rfq.hold", target_type="rfq", target_id=rfq.id, reason=reason)
    await db.commit()
    return _status(rfq, await service.deal_status_of(db, rfq))


@router.post("/rfqs/{rfq_id}/release", response_model=DeskStatus, response_model_by_alias=True)
async def release_rfq(rfq_id: str, payload: DeskReasonIn, admin: CanTriageRfqs, db: DbSession) -> DeskStatus:
    """Put a held RFQ back in the queue. The reason says what was checked."""
    reason = payload.reason
    rfq = await service.desk_release(db, parse_uuid(rfq_id))
    audit.record_action(db, admin=admin, action="rfq.release", target_type="rfq", target_id=rfq.id, reason=reason)
    await db.commit()
    return _status(rfq, await service.deal_status_of(db, rfq))


# ── Held countries and settings ──────────────────────────────────────


@router.get("/held-countries", response_model=ItemList[HeldCountryOut], response_model_by_alias=True)
async def list_held(_: CanTriageRfqs, db: DbSession) -> ItemList[HeldCountryOut]:
    return item_list([HeldCountryOut(code=h.code, reason=h.reason) for h in await service.list_held(db)])


@router.put("/held-countries/{code}", response_model=HeldCountryOut, response_model_by_alias=True)
async def hold_country(code: str, payload: HeldCountryIn, admin: CanConfigureTrade, db: DbSession) -> HeldCountryOut:
    row = await service.hold_country(db, code, payload.reason)
    audit.record_action(
        db, admin=admin, action="held_country.set", target_type="held_country", target_id=row.code,
        reason=payload.reason,
    )
    await db.commit()
    return HeldCountryOut(code=row.code, reason=row.reason)


@router.delete("/held-countries/{code}", status_code=204, response_class=Response)
async def release_country(code: str, admin: CanConfigureTrade, db: DbSession) -> Response:
    await service.release_country(db, code)
    audit.record_action(
        db, admin=admin, action="held_country.remove", target_type="held_country", target_id=code.strip().upper()
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/trade-settings", response_model=ItemList[TradeSettingOut], response_model_by_alias=True)
async def list_settings(_: CanTriageRfqs, db: DbSession) -> ItemList[TradeSettingOut]:
    return item_list([
        TradeSettingOut(key=s.key, value=s.value, is_placeholder=s.is_placeholder) for s in await service.list_settings(db)
    ])


@router.put("/trade-settings/{key}", response_model=TradeSettingOut, response_model_by_alias=True)
async def set_setting(key: str, payload: TradeSettingIn, admin: CanConfigureTrade, db: DbSession) -> TradeSettingOut:
    row, old = await service.set_setting(db, key, payload.value)
    audit.record_action(
        db, admin=admin, action="trade_setting.update", target_type="trade_setting", target_id=key,
        details={"from": str(old), "to": str(payload.value)},
    )
    await db.commit()
    return TradeSettingOut(key=row.key, value=row.value, is_placeholder=row.is_placeholder)
