from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.bank_details import BankDetails
from app.models.buyer import Buyer
from app.models.identity import Identity
from app.models.seller import Seller
from app.models.user import User
from app.schemas.me import (
    BankData,
    BusinessData,
    Completion,
    MeResponse,
    PrimaryData,
    SellerData,
)

router = APIRouter(tags=["me"])


def _primary_complete(b: Buyer | None) -> bool:
    return bool(
        b
        and b.full_name
        and b.email
        and b.address_line
        and b.city
        and b.state
        and b.pincode
    )


def _business_complete(s: Seller | None) -> bool:
    return bool(s and s.pan and s.company_name)


def _bank_complete(bd: BankDetails | None) -> bool:
    return bool(bd and bd.account_number and bd.ifsc and bd.holder_name)


def _seller_complete(s: Seller | None) -> bool:
    return bool(s and (s.udyam or s.aadhaar or s.tan))


@router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    buyer = await db.scalar(select(Buyer).where(Buyer.user_id == user.id))
    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    bank = await db.scalar(select(BankDetails).where(BankDetails.user_id == user.id))
    identity = await db.scalar(
        select(Identity).where(Identity.user_id == user.id).limit(1)
    )

    return MeResponse(
        user_id=str(user.id),
        user_type=user.user_type.value,
        status=user.status.value,
        mobile=identity.value if identity else "",
        full_name=buyer.full_name if buyer else None,
        completion=Completion(
            primary=_primary_complete(buyer),
            business=_business_complete(seller),
            bank=_bank_complete(bank),
            seller=_seller_complete(seller),
        ),
        primary=PrimaryData(
            full_name=buyer.full_name if buyer else None,
            email=buyer.email if buyer else None,
            address_line=buyer.address_line if buyer else None,
            city=buyer.city if buyer else None,
            state=buyer.state if buyer else None,
            pincode=buyer.pincode if buyer else None,
            alt_mobile=buyer.alt_mobile if buyer else None,
            alt_email=buyer.alt_email if buyer else None,
            business_email=buyer.business_email if buyer else None,
            website_url=buyer.website_url if buyer else None,
            google_business_url=buyer.google_business_url if buyer else None,
            facebook_url=buyer.facebook_url if buyer else None,
        ),
        business=BusinessData(
            gstin=seller.gstin if seller else None,
            pan=seller.pan if seller else None,
            company_name=seller.company_name if seller else None,
        ),
        bank=BankData(
            account_number=bank.account_number if bank else None,
            ifsc=bank.ifsc if bank else None,
            holder_name=bank.holder_name if bank else None,
            branch_name=bank.branch_name if bank else None,
            bank_name=bank.bank_name if bank else None,
        ),
        seller=SellerData(
            udyam=seller.udyam if seller else None,
            aadhaar=seller.aadhaar if seller else None,
            tan=seller.tan if seller else None,
        ),
    )
