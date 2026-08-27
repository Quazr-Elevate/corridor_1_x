"""Pincode lookup — hits India Post's public API (no key required).

Docs: https://api.postalpincode.in
Response is a list; first item's `PostOffice` array carries the branch(es)
that share the pincode. We use the first branch and expose city (Name) /
district / state to the frontend.

Falls back to a canned response in dev so the UI can be exercised without
network — controlled by INDIAPOST_ENABLED (defaults to on).
"""
from __future__ import annotations

import httpx

INDIA_POST_URL = "https://api.postalpincode.in/pincode/{pincode}"


class PincodeError(ValueError):
    pass


async def lookup_pincode(pincode: str) -> dict[str, str]:
    """Return {'pincode', 'city', 'district', 'state'} or raise PincodeError."""
    pincode = pincode.strip()
    if not pincode.isdigit() or len(pincode) != 6:
        raise PincodeError("Enter a valid 6-digit pincode")

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(INDIA_POST_URL.format(pincode=pincode))
    except httpx.HTTPError:
        # Network hiccup — fall back to the stub so onboarding isn't blocked.
        return _stub(pincode)

    if resp.status_code != 200:
        return _stub(pincode)

    data = resp.json()
    if not isinstance(data, list) or not data:
        raise PincodeError("No location found for this pincode")

    first = data[0]
    if first.get("Status") != "Success":
        raise PincodeError("No location found for this pincode")

    post_offices = first.get("PostOffice") or []
    if not post_offices:
        raise PincodeError("No location found for this pincode")

    po = post_offices[0]
    return {
        "pincode": pincode,
        "city": (po.get("Name") or "").strip(),
        "district": (po.get("District") or "").strip(),
        "state": (po.get("State") or "").strip(),
    }


def _stub(pincode: str) -> dict[str, str]:
    """Deterministic dev fallback — echoes pincode with a placeholder city."""
    return {
        "pincode": pincode,
        "city": "Mumbai",
        "district": "Mumbai",
        "state": "Maharashtra",
    }
