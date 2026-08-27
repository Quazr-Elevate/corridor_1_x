from fastapi import APIRouter, HTTPException

from app.providers.pincode import PincodeError, lookup_pincode
from app.schemas.base import CamelModel

router = APIRouter(tags=["pincode"])


class PincodeOut(CamelModel):
    pincode: str
    city: str
    district: str | None = None
    state: str


@router.get("/pincode/{pincode}", response_model=PincodeOut, response_model_by_alias=True)
async def get_pincode(pincode: str) -> PincodeOut:
    try:
        data = await lookup_pincode(pincode)
    except PincodeError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return PincodeOut(
        pincode=data["pincode"],
        city=data["city"],
        district=data.get("district") or None,
        state=data["state"],
    )
