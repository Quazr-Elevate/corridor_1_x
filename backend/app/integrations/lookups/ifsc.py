"""IFSC lookup via Razorpay's public IFSC API (no key).

Docs: https://razorpay.com/docs/api/utility/#ifsc-toolkit
Endpoint: ``GET https://ifsc.razorpay.com/{IFSC}``
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

IFSC_URL = "https://ifsc.razorpay.com/{code}"
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


class IfscInvalid(ValueError):
    pass


class IfscNotFound(Exception):
    pass


class IfscServiceError(Exception):
    pass


@dataclass(frozen=True)
class IfscResult:
    ifsc: str
    bank: str
    branch: str
    city: str | None
    state: str | None


class IfscLookup:
    def __init__(
        self,
        *,
        stub: bool = False,
        timeout: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.stub = stub
        self.timeout = timeout
        self.transport = transport

    async def lookup(self, ifsc: str) -> IfscResult:
        code = ifsc.strip().upper()
        if not _IFSC_RE.match(code):
            raise IfscInvalid("IFSC must be 11 characters (e.g. HDFC0001234)")
        if self.stub:
            return IfscResult(ifsc=code, bank="Stub Bank", branch="Main", city="Mumbai", state="Maharashtra")

        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                res = await client.get(IFSC_URL.format(code=code))
        except httpx.HTTPError as e:
            raise IfscServiceError("IFSC service is unreachable") from e
        if res.status_code == 404:
            raise IfscNotFound(f"No branch found for IFSC {code}")
        if res.status_code >= 400:
            raise IfscServiceError(f"IFSC lookup failed ({res.status_code})")
        try:
            data = res.json()
        except ValueError as e:
            raise IfscServiceError("IFSC service returned invalid JSON") from e
        return IfscResult(
            ifsc=code,
            bank=data.get("BANK", "") or "",
            branch=data.get("BRANCH", "") or "",
            city=data.get("CITY"),
            state=data.get("STATE"),
        )
