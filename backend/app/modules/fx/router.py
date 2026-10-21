"""GET /public/fx/rates — the latest stored USD rates (anonymous)."""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.modules.auth.deps import DbSession
from app.modules.fx.schemas import FxRatesOut
from app.modules.fx.service import get_latest_rates

router = APIRouter(prefix="/public/fx", tags=["public"])


@router.get("/rates", response_model=FxRatesOut, response_model_by_alias=True)
async def fx_rates(db: DbSession, response: Response) -> FxRatesOut:
    latest = await get_latest_rates(db)
    response.headers["Cache-Control"] = "public, max-age=300"
    return FxRatesOut(
        as_of=latest.as_of,
        rates={code: float(rate) for code, rate in latest.rates.items()},
        source=latest.source,
    )
