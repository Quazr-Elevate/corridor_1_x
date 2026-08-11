from typing import Literal

from app.schemas.base import CamelModel


class SellerCreate(CamelModel):
    onboarding_path: Literal["gstin", "pan"]
    gstin: str | None = None
    pan: str
    company_name: str
    business_type: str | None = None
    nature_of_business: str | None = None
    owner_name: str
    building: str | None = None
    pincode: str
    city: str
    district: str | None = None
    state: str
    country: str = "India"
    mobile: str
    email: str | None = None


class SellerCreated(CamelModel):
    id: str
    status: str
