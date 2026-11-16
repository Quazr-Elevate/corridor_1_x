"""/admin/rfqs/{id}/quotes, /admin/quotes/{id}/cost-sheet and
/admin/cost-sheets/* — from a seller's quote to the buyer's offer (build
plan 6.3–6.4). The cost sheet never leaves these routes."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.security import parse_uuid
from app.modules.admin import service as audit
from app.modules.admin.deps import CanApproveMargin, CanTriageRfqs
from app.modules.auth.deps import DbSession
from app.modules.quotes import service
from app.modules.quotes.schemas import CostSheetIn, CostSheetRead, DeskQuote, PublishedOffer, PublishIn
from app.shared.schemas import ItemList, item_list

router = APIRouter()


@router.get("/rfqs/{rfq_id}/quotes", response_model=ItemList[DeskQuote], response_model_by_alias=True)
async def list_quotes(rfq_id: str, _: CanTriageRfqs, db: DbSession) -> ItemList[DeskQuote]:
    return item_list(await service.desk_quotes(db, parse_uuid(rfq_id)))


@router.put("/quotes/{quote_id}/cost-sheet", response_model=CostSheetRead, response_model_by_alias=True)
async def save_cost_sheet(
    quote_id: str, payload: CostSheetIn, admin: CanTriageRfqs, db: DbSession
) -> CostSheetRead:
    """Cost a quote. The FX rate and buffer are read once and stored here."""
    sheet = await service.save_cost_sheet(db, admin.id, parse_uuid(quote_id), payload)
    audit.record_action(
        db, admin=admin, action="cost_sheet.save", target_type="cost_sheet", target_id=sheet.id,
        details={"margin_pct": str(sheet.margin_pct), "status": sheet.status},
    )
    await db.commit()
    return service.sheet_to_read(sheet)


@router.post("/cost-sheets/{sheet_id}/approve", response_model=CostSheetRead, response_model_by_alias=True)
async def approve_cost_sheet(sheet_id: str, admin: CanApproveMargin, db: DbSession) -> CostSheetRead:
    """Accept a margin under the floor. The approver cannot be the author."""
    sheet = await service.approve_cost_sheet(db, admin.id, parse_uuid(sheet_id))
    audit.record_action(
        db, admin=admin, action="cost_sheet.approve", target_type="cost_sheet", target_id=sheet.id,
        details={"margin_pct": str(sheet.margin_pct), "min_margin_pct": str(sheet.min_margin_pct)},
    )
    await db.commit()
    return service.sheet_to_read(sheet)


@router.post("/cost-sheets/{sheet_id}/publish", response_model=PublishedOffer, response_model_by_alias=True, status_code=201)
async def publish_offer(sheet_id: str, payload: PublishIn, admin: CanTriageRfqs, db: DbSession) -> PublishedOffer:
    """Send the offer to the buyer. The first offer moves the deal to QUOTED."""
    offer, deal = await service.publish_offer(db, admin.id, parse_uuid(sheet_id), payload.valid_until)
    audit.record_action(
        db, admin=admin, action="offer.publish", target_type="offer", target_id=offer.id,
        details={"deal": deal.code},
    )
    await db.commit()
    return PublishedOffer(
        id=str(offer.id), deal_code=deal.code, deal_status=deal.status, price_minor=offer.price_minor,
        currency=offer.currency, valid_until=offer.valid_until,
    )
