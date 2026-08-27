"""IFSC lookup via Razorpay's public IFSC API — free, no auth key required.

Docs: https://razorpay.com/docs/api/utility/#ifsc-toolkit
Endpoint: GET https://ifsc.razorpay.com/{IFSC}
"""

from __future__ import annotations

import httpx


class IfscNotFound(Exception):
    pass


class IfscServiceError(Exception):
    pass


async def lookup_ifsc(ifsc: str) -> dict:
    code = ifsc.strip().upper()
    if len(code) != 11:
        raise ValueError("IFSC must be 11 characters")

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            res = await client.get(f"https://ifsc.razorpay.com/{code}")
        except httpx.RequestError as e:
            raise IfscServiceError("IFSC service is unreachable") from e

    if res.status_code == 404:
        raise IfscNotFound(f"No branch found for IFSC {code}")
    if res.status_code >= 400:
        raise IfscServiceError(f"IFSC lookup failed ({res.status_code})")

    data = res.json()
    return {
        "ifsc": code,
        "bank": data.get("BANK", ""),
        "branch": data.get("BRANCH", ""),
        "city": data.get("CITY"),
        "state": data.get("STATE"),
    }
