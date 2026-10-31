"""/me and /onboarding/* — the signed-in user's own account."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Response, UploadFile

from app.core.security import SESSION_COOKIE, clear_cookie
from app.modules.accounts import service
from app.modules.accounts.schemas import (
    BusinessProfileIn,
    BusinessProfileSaveIn,
    ImageUploaded,
    CompanyInfoIn,
    MeResponse,
    MeUpdate,
    OnboardingSaved,
    OnboardingStatus,
    PrimaryContactIn,
    VerificationState,
)
from app.modules.auth.deps import CurrentUser, DbSession
from app.shared.files import file_response

me_router = APIRouter(tags=["me"])
onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"])
branding_router = APIRouter(tags=["uploads"])

BrandingSlot = Literal["logo", "banner"]


@me_router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    return await service.me_view(db, user)


@me_router.patch("/me", response_model=MeResponse, response_model_by_alias=True)
async def update_me(payload: MeUpdate, user: CurrentUser, db: DbSession) -> MeResponse:
    """Update personal preferences — ``displayCurrency``, ``tourCompleted``."""
    return await service.update_me(db, user, payload)


@me_router.put("/me/business-profile", response_model=MeResponse, response_model_by_alias=True)
async def save_business_profile_v2(payload: BusinessProfileSaveIn, user: CurrentUser, db: DbSession) -> MeResponse:
    """Company name, registered address and country (business profile)."""
    return await service.save_profile(db, user, payload)


@me_router.post(
    "/me/business/{slot}", response_model=ImageUploaded, response_model_by_alias=True, status_code=201
)
async def upload_branding(slot: BrandingSlot, user: CurrentUser, db: DbSession, file: UploadFile = File(...)) -> ImageUploaded:
    """Business logo or banner — JPG/PNG/WEBP (sniffed), ≤ 5 MB. Public."""
    content = await file.read(service.MAX_IMAGE_BYTES + 1)
    return ImageUploaded(url=await service.set_branding_image(db, user, slot, content))


@me_router.delete("/me/business/{slot}", status_code=204, response_class=Response)
async def delete_branding(slot: BrandingSlot, user: CurrentUser, db: DbSession) -> Response:
    await service.clear_branding_image(db, user, slot)
    return Response(status_code=204)


@branding_router.get("/uploads/branding/{filename}")
async def branding_image(filename: str) -> Response:
    data = await service.read_branding_image(filename)
    return file_response(data, cache_control="public, max-age=86400, immutable")


@me_router.post("/me/submit-verification", response_model=VerificationState, response_model_by_alias=True)
async def submit_verification(user: CurrentUser, db: DbSession) -> VerificationState:
    return await service.submit_for_verification(db, user)


@me_router.delete("/me", status_code=204, response_class=Response)
async def delete_me(user: CurrentUser, db: DbSession) -> Response:
    await service.delete_account(db, user)
    response = Response(status_code=204)
    clear_cookie(response, SESSION_COOKIE)
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
