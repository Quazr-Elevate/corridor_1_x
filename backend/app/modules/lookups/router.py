"""GET /pincode/{pincode} and GET /ifsc/{code} — thin wrappers over the
lookup integrations. Lookup clients are dependencies so tests can swap
them (``app.dependency_overrides``)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.errors import BadRequest, NotFound, UpstreamError
from app.integrations.lookups import (
    IfscInvalid,
    IfscLookup,
    IfscNotFound,
    IfscServiceError,
    PincodeError,
    PincodeLookup,
    PincodeServiceError,
)
from app.shared.schemas import CamelModel

router = APIRouter(tags=["lookups"])


class PincodeOut(CamelModel):
    pincode: str
    city: str
    district: str | None = None
    state: str


class IfscOut(CamelModel):
    ifsc: str
    bank: str
    branch: str
    city: str | None = None
    state: str | None = None


def get_pincode_lookup() -> PincodeLookup:
    return PincodeLookup(stub=settings.lookups_stub)


def get_ifsc_lookup() -> IfscLookup:
    return IfscLookup(stub=settings.lookups_stub)


@router.get("/pincode/{pincode}", response_model=PincodeOut, response_model_by_alias=True)
async def get_pincode(
    pincode: str, lookup: Annotated[PincodeLookup, Depends(get_pincode_lookup)]
) -> PincodeOut:
    try:
        r = await lookup.lookup(pincode)
    except PincodeError as e:
        raise NotFound(str(e)) from e
    except PincodeServiceError as e:
        raise UpstreamError("Pincode service unavailable, enter city/state manually") from e
    return PincodeOut(pincode=r.pincode, city=r.city, district=r.district, state=r.state)


@router.get("/ifsc/{code}", response_model=IfscOut, response_model_by_alias=True)
async def get_ifsc(code: str, lookup: Annotated[IfscLookup, Depends(get_ifsc_lookup)]) -> IfscOut:
    try:
        r = await lookup.lookup(code)
    except IfscInvalid as e:
        raise BadRequest(str(e)) from e
    except IfscNotFound as e:
        raise NotFound(str(e)) from e
    except IfscServiceError as e:
        raise UpstreamError(str(e)) from e
    return IfscOut(ifsc=r.ifsc, bank=r.bank, branch=r.branch, city=r.city, state=r.state)
