"""/admin/credits/* — what paid actions cost and what plans are on sale.

Prices are a client decision (plan 17.5); rows seeded as placeholders say so
until someone with ``credits.manage`` sets them. Every change is audited."""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.admin import service
from app.modules.admin.deps import CanManageCredits
from app.modules.auth.deps import DbSession
from app.modules.credits import service as credits
from app.modules.credits.schemas import (
    AdminPlanRead,
    PlanUpdate,
    PriceRead,
    PriceUpdate,
    SpendAction,
    admin_plan_to_read,
    price_to_read,
)
from app.shared.schemas import ItemList, item_list

router = APIRouter(prefix="/credits")


@router.get("/prices", response_model=ItemList[PriceRead], response_model_by_alias=True)
async def list_prices(_: CanManageCredits, db: DbSession) -> ItemList[PriceRead]:
    return item_list([price_to_read(p) for p in await credits.list_prices(db)])


@router.put("/prices/{action}", response_model=PriceRead, response_model_by_alias=True)
async def set_price(action: SpendAction, payload: PriceUpdate, admin: CanManageCredits, db: DbSession) -> PriceRead:
    price, old = await credits.set_price(db, action, payload.credits)
    service.record_action(
        db, admin=admin, action="credit_price.update", target_type="credit_price", target_id=action,
        details={"from": old, "to": payload.credits},
    )
    await db.commit()
    return price_to_read(price)


@router.get("/plans", response_model=ItemList[AdminPlanRead], response_model_by_alias=True)
async def list_plans(_: CanManageCredits, db: DbSession) -> ItemList[AdminPlanRead]:
    return item_list([admin_plan_to_read(p) for p in await credits.list_plans(db, active_only=False)])


@router.put("/plans/{code}", response_model=AdminPlanRead, response_model_by_alias=True)
async def update_plan(code: str, payload: PlanUpdate, admin: CanManageCredits, db: DbSession) -> AdminPlanRead:
    plan, changed = await credits.update_plan(db, code, payload)
    if changed:
        service.record_action(
            db, admin=admin, action="credit_plan.update", target_type="credit_plan", target_id=plan.code,
            details={"fields": changed},
        )
    await db.commit()
    await db.refresh(plan)
    return admin_plan_to_read(plan)
