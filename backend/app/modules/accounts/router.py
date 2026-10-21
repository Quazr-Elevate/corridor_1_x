"""/me and /onboarding/* — the signed-in user's own account."""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.security import clear_session_cookie
from app.modules.accounts import service
from app.modules.accounts.schemas import (
    BusinessProfileIn,
    CompanyInfoIn,
    MeResponse,
    MeUpdate,
    OnboardingSaved,
    OnboardingStatus,
    PrimaryContactIn,
    VerificationState,
)
from app.modules.auth.deps import CurrentUser, DbSession

me_router = APIRouter(tags=["me"])
onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@me_router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    return await service.me_view(db, user)


@me_router.patch("/me", response_model=MeResponse, response_model_by_alias=True)
async def update_me(payload: MeUpdate, user: CurrentUser, db: DbSession) -> MeResponse:
    """Update personal preferences — today ``{"displayCurrency": "AED"}``."""
    return await service.update_me(db, user, payload)


@me_router.post("/me/submit-verification", response_model=VerificationState, response_model_by_alias=True)
async def submit_verification(user: CurrentUser, db: DbSession) -> VerificationState:
    return await service.submit_for_verification(db, user)


@me_router.delete("/me", status_code=204, response_class=Response)
async def delete_me(user: CurrentUser, db: DbSession) -> Response:
    await service.delete_account(db, user)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@onboarding_router.get("/status", response_model=OnboardingStatus, response_model_by_alias=True)
async def onboarding_status(user: CurrentUser, db: DbSession) -> OnboardingStatus:
    return await service.get_onboarding_status(db, user)


@onboarding_router.post("/company", response_model=OnboardingSaved, response_model_by_alias=True)
async def save_company_info(payload: CompanyInfoIn, user: CurrentUser, db: DbSession) -> OnboardingSaved:
    return OnboardingSaved(ok=True, status=await service.save_company_info(db, user, payload))


@onboarding_router.post("/contact", response_model=OnboardingSaved, response_model_by_alias=True)
async def save_primary_contact(payload: PrimaryContactIn, user: CurrentUser, db: DbSession) -> OnboardingSaved:
    return OnboardingSaved(ok=True, status=await service.save_primary_contact(db, user, payload))


@onboarding_router.post("/business", response_model=OnboardingSaved, response_model_by_alias=True)
async def save_business_profile(payload: BusinessProfileIn, user: CurrentUser, db: DbSession) -> OnboardingSaved:
    return OnboardingSaved(ok=True, status=await service.save_business_profile(db, user, payload))
