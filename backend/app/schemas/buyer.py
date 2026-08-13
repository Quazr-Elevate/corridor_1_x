from pydantic import field_validator

from app.schemas.base import CamelModel
from app.validators import PERSON_NAME_REGEX


class BuyerCreate(CamelModel):
    full_name: str
    company_name: str
    country: str
    city: str | None = None
    mobile: str
    email: str | None = None

    @field_validator("full_name")
    @classmethod
    def _validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if not PERSON_NAME_REGEX.match(v):
            raise ValueError(
                "Full name must be letters, spaces, hyphens, apostrophes, or periods only"
            )
        return v


class BuyerCreated(CamelModel):
    id: str
    status: str
