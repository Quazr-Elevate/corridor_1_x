"""/admin/rfqs/{id}/quotes, /admin/quotes/{id}/cost-sheet and
/admin/cost-sheets/* — from a seller's quote to the buyer's offer (build
plan 6.3–6.4). The cost sheet never leaves these routes."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app import notifications

from app.core.security import parse_uuid
from app.models.rfq import Rfq
from app.modules.accounts.service import owner_contact
from app.modules.admin import service as audit
from app.modules.admin.deps import CanApproveMargin, CanTriageRfqs
from app.modules.auth.deps import DbSession
from app.modules.quotes import service
from app.modules.admin.schemas import AccessReasonIn
from app.modules.quotes.schemas import CostSheetIn, CostSheetRead, DeskQuote, OfferWithdrawn, PublishedOffer, PublishIn
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
async def publish_offer(
    sheet_id: str, payload: PublishIn, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks
) -> PublishedOffer:
    """Send the offer to the buyer. The first offer moves the deal to QUOTED.
    The buyer is told an offer is waiting; the seller that their quote went
    forward (CX-183)."""
    offer, deal = await service.publish_offer(db, admin.id, parse_uuid(sheet_id), payload.valid_until)
    audit.record_action(
        db, admin=admin, action="offer.publish", target_type="offer", target_id=offer.id,
        details={"deal": deal.code},
    )
    rfq = await db.get(Rfq, offer.rfq_id)
    buyer, seller = await owner_contact(db, offer.buyer_business_id), await owner_contact(db, offer.seller_business_id)
    await db.commit()
    if buyer is not None:
        background.add_task(
            notifications.deliver_safely, notifications.send_offer_published, to=buyer.email,
            first_name=notifications.first_name_of(buyer.full_name), category=rfq.category, rfq_id=str(rfq.id),
            valid_until=offer.valid_until,
        )
    if seller is not None:
        background.add_task(
            notifications.deliver_safely, notifications.send_quote_forwarded, to=seller.email,
            first_name=notifications.first_name_of(seller.full_name), category=rfq.category, rfq_id=str(rfq.id),
        )
    return PublishedOffer(
        id=str(offer.id), deal_code=deal.code, deal_status=deal.status, price_minor=offer.price_minor,
        currency=offer.currency, valid_until=offer.valid_until,
    )


@router.post("/offers/{offer_id}/withdraw", response_model=OfferWithdrawn, response_model_by_alias=True)
async def withdraw_offer(offer_id: str, payload: AccessReasonIn, admin: CanTriageRfqs, db: DbSession) -> OfferWithdrawn:
    """Take a published offer back from the buyer, with a reason (audited)."""
    offer = await service.withdraw_offer(db, parse_uuid(offer_id))
    audit.record_action(
        db, admin=admin, action="offer.withdraw", target_type="offer", target_id=offer.id, reason=payload.reason,
        details={"rfqId": str(offer.rfq_id)},
    )
    await db.commit()
    return OfferWithdrawn(id=str(offer.id), status=offer.status)
