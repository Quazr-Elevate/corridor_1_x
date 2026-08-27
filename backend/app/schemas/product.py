from decimal import Decimal
from typing import Literal

from app.schemas.base import CamelModel

Category = Literal[
    "Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds",
    "Cotton", "Millets", "Tea", "Coffee", "Other",
]

Unit = Literal["MT", "kg", "quintal"]

Packaging = Literal["Jute", "PP woven", "HDPE", "Bulk", "Other"]


class ProductCreate(CamelModel):
    name: str
    category: Category
    variety: str | None = None
    origin_state: str | None = None
    packaging: Packaging | None = None
    quantity: Decimal | None = None
    unit: Unit = "MT"
    moq: Decimal | None = None
    price_per_unit: Decimal | None = None
    description: str | None = None
    # At least one required. Enforced in the router with a clear message
    # (Pydantic's min_length message is fine but the router message is nicer).
    photos: list[str] = []


class ProductRead(CamelModel):
    id: str
    name: str
    category: str
    variety: str | None = None
    origin_state: str | None = None
    packaging: str | None = None
    quantity: Decimal | None = None
    unit: str
    moq: Decimal | None = None
    price_per_unit: Decimal | None = None
    description: str | None = None
    photos: list[str] = []


class PhotoUploaded(CamelModel):
    url: str
