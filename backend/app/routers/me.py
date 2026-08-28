from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Response

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.identity import Identity
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User
from app.pii import mask_aadhaar, mask_bank_account
from app.user_session import clear_session_cookie
from app.schemas.me import (
    BankData,
    BusinessData,
    Completion,
    MeResponse,
    PrimaryData,
    RegulatoryData,
)

router = APIRouter(tags=["me"])


def _primary_complete(p: Profile | None) -> bool:
    return bool(
        p
        and p.full_name
        and p.email
        and p.address_line
        and p.city
        and p.state
        and p.pincode
    )


def _business_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.pan and bp.company_name)


def _bank_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.bank_account_number and bp.bank_ifsc and bp.bank_holder_name)


def _regulatory_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and (bp.udyam or bp.aadhaar or bp.tan))


@router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    )
    identity = await db.scalar(
        select(Identity).where(Identity.user_id == user.id).limit(1)
    )
    product_count = await db.scalar(
        select(func.count(Product.id)).where(Product.user_id == user.id)
    ) or 0

    return MeResponse(
        user_id=str(user.id),
        # Role is derived: any product means seller.
        user_type="seller" if product_count > 0 else "buyer",
        status=user.status.value,
        mobile=identity.value if identity else "",
        full_name=profile.full_name if profile else None,
        completion=Completion(
            primary=_primary_complete(profile),
            business=_business_complete(business),
            bank=_bank_complete(business),
            seller=_regulatory_complete(business),
        ),
        primary=PrimaryData(
            full_name=profile.full_name if profile else None,
            email=profile.email if profile else None,
            address_line=profile.address_line if profile else None,
            city=profile.city if profile else None,
            state=profile.state if profile else None,
            pincode=profile.pincode if profile else None,
            country=profile.country if profile else None,
            alt_mobile=profile.alt_mobile if profile else None,
            alt_email=profile.alt_email if profile else None,
            business_email=profile.business_email if profile else None,
            website_url=profile.website_url if profile else None,
            google_business_url=profile.google_business_url if profile else None,
            facebook_url=profile.facebook_url if profile else None,
        ),
        business=BusinessData(
            gstin=business.gstin if business else None,
            pan=business.pan if business else None,
            company_name=business.company_name if business else None,
            business_type=business.business_type if business else None,
            nature_of_business=business.nature_of_business if business else None,
        ),
        bank=BankData(
            # PII: mask account number in wire response. The user filled it
            # themselves; showing them the masked value is enough to confirm
            # "yes, this is the account I set". Full value stays in DB.
            account_number=mask_bank_account(business.bank_account_number) if business else None,
            ifsc=business.bank_ifsc if business else None,
            holder_name=business.bank_holder_name if business else None,
            branch_name=business.bank_branch_name if business else None,
            bank_name=business.bank_name if business else None,
        ),
        seller=RegulatoryData(
            udyam=business.udyam if business else None,
            # PII: Aadhaar Act mandates masking on display.
            aadhaar=mask_aadhaar(business.aadhaar) if business else None,
            tan=business.tan if business else None,
        ),
    )


# ── DPDP right-to-erasure ───────────────────────────────────────────────────


@router.delete("/me", status_code=204)
async def delete_me(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete the current account.

    Under DPDP (India) and PDPL (UAE) users have a right-to-erasure.
    This handler:
      1. Marks `users.deleted_at = now()`  (auth stops working immediately)
      2. Wipes personal fields on the profile row (name, email, address,
         alt contacts, socials) so the row can't be read even by admin
      3. Nulls the phone value on all identities (frees the number so
         the person can sign up again with the same phone later)
      4. Clears the session cookie

    Business profile / products are kept because they may be part of a
    counterparty's audit trail; admin can hard-delete via ops if the user
    insists. Hard-delete of soft-deleted rows happens via cleanup job later.
    """
    now = datetime.now(tz=timezone.utc)
    user.deleted_at = now

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is not None:
        profile.full_name = f"deleted-{user.id}"
        profile.email = None
        profile.address_line = None
        profile.city = None
        profile.state = None
        profile.pincode = None
        profile.alt_mobile = None
        profile.alt_email = None
        profile.business_email = None
        profile.website_url = None
        profile.google_business_url = None
        profile.facebook_url = None

    # Break identity->phone/email link so the values are free for reuse.
    idents = list(await db.scalars(select(Identity).where(Identity.user_id == user.id)))
    for ident in idents:
        # Set to a unique unusable value so the UNIQUE(value) constraint
        # holds without pointing at a real login.
        ident.value = f"deleted-{uuid4().hex}"

    await db.commit()
    clear_session_cookie(response)
    return Response(status_code=204)
