"""GET /pincode/{pincode} and GET /ifsc/{code} — thin wrappers over the
lookup integrations, for signed-in traders and admins only. Lookup clients
are dependencies so tests can swap them (``app.dependency_overrides``).

Both upstreams are free public services, so a principal gets 30 calls a
minute and a successful answer is remembered for a day.
"""
from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import BadRequest, NotFound, Unauthorized, UpstreamError
from app.core.logging import set_actor
from app.core.security import ADMIN_COOKIE, SESSION_COOKIE
from app.integrations.lookups import (
    IfscInvalid,
    IfscLookup,
    IfscNotFound,
    IfscServiceError,
    PincodeError,
    PincodeLookup,
    PincodeServiceError,
)
from app.modules.admin.deps import require as require_admin
from app.modules.auth.deps import resolve_session_user
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.schemas import CamelModel

LOOKUP_PER_PRINCIPAL = RateLimitRule("lookups:principal", limit=30, window_sec=60)
CACHE_TTL_SEC = 24 * 60 * 60
# PIN codes and branch codes are finite; the cap only bounds a hostile sweep.
CACHE_MAX_ENTRIES = 20_000

_signed_in_admin = require_admin(None)
_cache: dict[tuple[str, str], tuple[float, CamelModel]] = {}

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


def _cached(kind: str, key: str) -> CamelModel | None:
    hit = _cache.get((kind, key))
    if hit is None:
        return None
    stored_at, value = hit
    if time.monotonic() - stored_at > CACHE_TTL_SEC:
        del _cache[(kind, key)]
        return None
    return value


def _remember(kind: str, key: str, value: CamelModel) -> None:
    if len(_cache) >= CACHE_MAX_ENTRIES:
        # Dicts keep insertion order, so the first key is the oldest.
        del _cache[next(iter(_cache))]
    _cache[(kind, key)] = (time.monotonic(), value)


def clear_cache() -> None:
    _cache.clear()


async def lookup_principal(
    request: Request,
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> str:
    """A signed-in trader or admin, rate limited; returns the limiter key."""
    found = await resolve_session_user(db, cor1x_session)
    if found is not None:
        set_actor("user", found[0].id)
        key = f"user:{found[0].id}"
    elif cor1x_admin:
        admin = await _signed_in_admin(request, cor1x_admin, db)
        key = f"admin:{admin.id}"
    else:
        raise Unauthorized("Not signed in")
    await get_limiter().check(LOOKUP_PER_PRINCIPAL, key)
    return key


LookupPrincipal = Annotated[str, Depends(lookup_principal)]


def get_pincode_lookup() -> PincodeLookup:
    return PincodeLookup(stub=settings.lookups_stub)


def get_ifsc_lookup() -> IfscLookup:
    return IfscLookup(stub=settings.lookups_stub)


@router.get("/pincode/{pincode}", response_model=PincodeOut, response_model_by_alias=True)
async def get_pincode(
    pincode: str, _: LookupPrincipal, lookup: Annotated[PincodeLookup, Depends(get_pincode_lookup)]
) -> PincodeOut:
    key = pincode.strip()
    if (hit := _cached("pincode", key)) is not None:
        return hit
    try:
        r = await lookup.lookup(key)
    except PincodeError as e:
        raise NotFound(str(e)) from e
    except PincodeServiceError as e:
        raise UpstreamError("Pincode service unavailable, enter city/state manually") from e
    out = PincodeOut(pincode=r.pincode, city=r.city, district=r.district, state=r.state)
    _remember("pincode", key, out)
    return out


@router.get("/ifsc/{code}", response_model=IfscOut, response_model_by_alias=True)
async def get_ifsc(
    code: str, _: LookupPrincipal, lookup: Annotated[IfscLookup, Depends(get_ifsc_lookup)]
) -> IfscOut:
    key = code.strip().upper()
    if (hit := _cached("ifsc", key)) is not None:
        return hit
    try:
        r = await lookup.lookup(key)
    except IfscInvalid as e:
        raise BadRequest(str(e)) from e
    except IfscNotFound as e:
        raise NotFound(str(e)) from e
    except IfscServiceError as e:
        raise UpstreamError(str(e)) from e
    out = IfscOut(ifsc=r.ifsc, bank=r.bank, branch=r.branch, city=r.city, state=r.state)
    _remember("ifsc", key, out)
    return out
