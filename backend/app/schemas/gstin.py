from app.schemas.base import CamelModel


class Address(CamelModel):
    building: str | None = None
    city: str
    district: str | None = None
    state: str
    pincode: str


class GstinLookup(CamelModel):
    gstin: str
    legal_name: str
    trade_name: str | None = None
    pan: str
    business_type: str
    nature_of_business: str | None = None
    masked_mobile: str = ""
    address: Address
