"""Current-user endpoints — /me GET + DELETE."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.pii import mask_bank_account
from app.schemas.me import (
    BankData,
    BusinessData,
    Completion,
    MeResponse,
    PrimaryData,
    VerificationState,
)
from app.user_session import clear_session_cookie
from app.verification import (
    MANDATORY_FIELDS,
    is_profile_complete,
    missing_mandatory_keys,
)

router = APIRouter(tags=["me"])


def _primary_complete(p: Profile | None) -> bool:
    return bool(
        p
        and p.full_name
        and p.address_line
        and p.city
        and p.state
        and p.pincode
    )


def _business_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and (bp.business_type or bp.nature_of_business))


def _bank_complete(bp: BusinessProfile | None) -> bool:
    return bool(bp and bp.bank_account_number and bp.bank_ifsc and bp.bank_holder_name)


@router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    # Single query pulls user + profile + business_profile via a left join,
    # eliminating two round-trips to Railway Postgres. Product count still
    # runs separately since it's an aggregate, not a relationship.
    row = await db.execute(
        select(User)
        .options(
            joinedload(User.profile),
            joinedload(User.business_profile),
        )
        .where(User.id == user.id)
    )
    hydrated = row.scalar_one()
    profile = hydrated.profile
    business = hydrated.business_profile
    product_count = await db.scalar(
        select(func.count(Product.id)).where(Product.user_id == user.id)
    ) or 0

    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        email_verified_at=user.email_verified_at,
        business_name=user.business_name,
        user_type="seller" if product_count > 0 else "buyer",
        status=user.status.value,
        must_change_password=user.must_change_password,
        completion=Completion(
            primary=_primary_complete(profile),
            business=_business_complete(business),
            bank=_bank_complete(business),
        ),
        verification=VerificationState(
            status=user.status.value,
            missing=missing_mandatory_keys(profile, business),
            mandatory_total=len(MANDATORY_FIELDS),
            submitted_at=user.verification_submitted_at,
            verified_at=user.verified_at,
            rejected_reason=user.verification_rejected_reason,
        ),
        primary=PrimaryData(
            full_name=profile.full_name if profile else None,
            phone=profile.phone if profile else None,
            department=profile.department if profile else None,
            position=profile.position if profile else None,
            address_line=profile.address_line if profile else None,
            city=profile.city if profile else None,
            state=profile.state if profile else None,
            pincode=profile.pincode if profile else None,
            country=profile.country if profile else None,
            website_url=profile.website_url if profile else None,
            google_business_url=profile.google_business_url if profile else None,
            facebook_url=profile.facebook_url if profile else None,
        ),
        business=BusinessData(
            legal_name=business.legal_name if business else None,
            industry=business.industry if business else None,
            operating_countries=business.operating_countries if business else None,
            website_url=business.website_url if business else None,
            trade_position=business.trade_position if business else None,
            seller_type=business.seller_type if business else None,
            business_role=business.business_role if business else None,
            export_status=business.export_status if business else None,
            target_markets=business.target_markets if business else None,
            target_buyer_types=business.target_buyer_types if business else None,
            main_objective=business.main_objective if business else None,
            company_introduction=business.company_introduction if business else None,
            business_type=business.business_type if business else None,
            nature_of_business=business.nature_of_business if business else None,
            udyam=business.udyam if business else None,
        ),
        bank=BankData(
            # PII: mask account number in wire response.
            account_number=mask_bank_account(business.bank_account_number) if business else None,
            ifsc=business.bank_ifsc if business else None,
            ifsc_verified_at=business.ifsc_verified_at if business else None,
            holder_name=business.bank_holder_name if business else None,
            branch_name=business.bank_branch_name if business else None,
            bank_name=business.bank_name if business else None,
        ),
    )


@router.post(
    "/me/submit-verification",
    response_model=VerificationState,
    response_model_by_alias=True,
)
async def submit_verification(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationState:
    """User-triggered action: send the profile for admin verification.

    Replaces the earlier auto-flip behaviour — submission is now an
    explicit intent (the "Send for verification" button in My Account),
    so a user editing a field no longer accidentally submits.

    Rules:
      * All seven mandatory fields must be filled, else 400.
      * ``verified`` users can't resubmit (they already have the badge).
      * ``pending_verification`` is idempotent — returning current state
        is a successful no-op so the UI handles double-clicks cleanly.
      * ``rejected`` users ARE allowed to resubmit, which clears the
        prior admin reason.
    """
    row = await db.execute(
        select(User)
        .options(
            joinedload(User.profile),
            joinedload(User.business_profile),
        )
        .where(User.id == user.id)
    )
    hydrated = row.scalar_one()
    profile = hydrated.profile
    business = hydrated.business_profile

    # Capture the completeness snapshot BEFORE any commit so the ORM
    # objects stay attached. Reaching the commit path means every
    # mandatory field is filled, so ``missing`` on the response is just
    # the empty list.
    missing_before = missing_mandatory_keys(profile, business)
    if missing_before:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fill every mandatory field before submitting. "
                f"Missing: {', '.join(missing_before)}."
            ),
        )

    if hydrated.status == UserStatus.verified:
        raise HTTPException(
            status_code=400,
            detail="You're already verified — nothing to submit.",
        )

    if hydrated.status != UserStatus.pending_verification:
        hydrated.status = UserStatus.pending_verification
        hydrated.verification_submitted_at = datetime.now(tz=timezone.utc)
        hydrated.verification_rejected_reason = None
        await db.commit()
        # Re-read status + audit columns off the fresh row — this
        # avoids touching the expired profile/business relationships.
        hydrated = await db.scalar(select(User).where(User.id == user.id))

    return VerificationState(
        status=hydrated.status.value,
        missing=[],
        mandatory_total=len(MANDATORY_FIELDS),
        submitted_at=hydrated.verification_submitted_at,
        verified_at=hydrated.verified_at,
        rejected_reason=hydrated.verification_rejected_reason,
    )


@router.delete("/me", status_code=204)
async def delete_me(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete the current account (DPDP right-to-erasure)."""
    now = datetime.now(tz=timezone.utc)
    user.deleted_at = now
    # Anonymise the login handle so the email can be reused if the person
    # signs up again later.
    user.email = f"deleted-{user.id}@deleted.local"

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is not None:
        profile.full_name = f"deleted-{user.id}"
        profile.address_line = None
        profile.city = None
        profile.state = None
        profile.pincode = None
        profile.website_url = None
        profile.google_business_url = None
        profile.facebook_url = None

    await db.commit()
    clear_session_cookie(response)
    return Response(status_code=204)
