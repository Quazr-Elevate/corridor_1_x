from typing import Literal

from pydantic import field_validator

from app.schemas.base import CamelModel
from app.validators import PERSON_NAME_REGEX


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

    @field_validator("owner_name")
    @classmethod
    def _validate_owner_name(cls, v: str) -> str:
        v = v.strip()
        if not PERSON_NAME_REGEX.match(v):
            raise ValueError(
                "Owner name must be letters, spaces, hyphens, apostrophes, or periods only"
            )
        return v


class SellerCreated(CamelModel):
    id: str
    status: str
