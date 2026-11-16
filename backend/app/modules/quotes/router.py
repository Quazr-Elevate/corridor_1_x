"""A seller's quote on a matched RFQ, and a buyer's offers on their own RFQ.
No route here returns a cost sheet or a purchase price to a buyer."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.quotes import service
from app.modules.quotes.schemas import OfferList, OfferRead, QuoteIn, QuoteRead
from app.ratelimit import RateLimitRule, get_limiter

quotes_router = APIRouter(prefix="/matched-rfqs", tags=["quotes"])
rfq_offers_router = APIRouter(prefix="/rfqs", tags=["offers"])
offers_router = APIRouter(prefix="/offers", tags=["offers"])

QUOTE_SAVES = RateLimitRule("quote.save:business", limit=120, window_sec=60 * 60)
UNLOCKS = RateLimitRule("offer.unlock:business", limit=120, window_sec=60 * 60)


@quotes_router.put("/{rfq_id}/quote", response_model=QuoteRead, response_model_by_alias=True)
async def save_quote(rfq_id: str, payload: QuoteIn, user: CurrentUser, db: DbSession) -> QuoteRead:
    """Quote on a matched RFQ, or revise the quote. PUT: one quote per seller per RFQ."""
    await get_limiter().check(QUOTE_SAVES, str(user.business_id))
    return await service.quote_to_read(db, await service.save_quote(db, user, parse_uuid(rfq_id), payload))


@quotes_router.get("/{rfq_id}/quote", response_model=QuoteRead, response_model_by_alias=True)
async def get_quote(rfq_id: str, user: CurrentUser, db: DbSession) -> QuoteRead:
    return await service.quote_to_read(db, await service.own_quote(db, user, parse_uuid(rfq_id)))


@rfq_offers_router.get("/{rfq_id}/offers", response_model=OfferList, response_model_by_alias=True)
async def list_offers(rfq_id: str, user: CurrentUser, db: DbSession) -> OfferList:
    offers = await service.list_offers(db, user, parse_uuid(rfq_id))
    return OfferList(total=len(offers), items=offers)


@offers_router.post("/{offer_id}/unlock", response_model=OfferRead, response_model_by_alias=True)
async def unlock_offer(offer_id: str, user: CurrentUser, db: DbSession) -> OfferRead:
    """See an offer's price and terms. Spends OFFER_UNLOCK the first time."""
    await get_limiter().check(UNLOCKS, str(user.business_id))
    return await service.unlock_offer(db, user, parse_uuid(offer_id))
