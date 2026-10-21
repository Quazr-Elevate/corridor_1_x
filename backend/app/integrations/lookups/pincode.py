"""Indian pincode lookup via India Post's public API (no key).

Docs: https://api.postalpincode.in — the response is a list whose first
item's ``PostOffice`` array holds the branches sharing the pincode.

Network/upstream failures raise :class:`PincodeServiceError` — callers
must surface that (the UI lets the user type city/state manually). A
canned response is only returned when the client is built with
``stub=True`` (explicit offline-dev setting).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

INDIA_POST_URL = "https://api.postalpincode.in/pincode/{pincode}"


class PincodeError(ValueError):
    """Invalid or unknown pincode (user error)."""


class PincodeServiceError(Exception):
    """Upstream unreachable / misbehaving."""


@dataclass(frozen=True)
class PincodeResult:
    pincode: str
    city: str
    district: str | None
    state: str


class PincodeLookup:
    def __init__(
        self,
        *,
        stub: bool = False,
        timeout: float = 6.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.stub = stub
        self.timeout = timeout
        self.transport = transport

    async def lookup(self, pincode: str) -> PincodeResult:
        pincode = pincode.strip()
        if not pincode.isdigit() or len(pincode) != 6 or pincode[0] == "0":
            raise PincodeError("Enter a valid 6-digit pincode")
        if self.stub:
            return PincodeResult(pincode=pincode, city="Mumbai", district="Mumbai", state="Maharashtra")

        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                resp = await client.get(INDIA_POST_URL.format(pincode=pincode))
        except httpx.HTTPError as e:
            raise PincodeServiceError("Pincode service unreachable") from e
        if resp.status_code != 200:
            raise PincodeServiceError(f"Pincode service returned {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise PincodeServiceError("Pincode service returned invalid JSON") from e

        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise PincodeError("No location found for this pincode")
        first = data[0]
        offices = first.get("PostOffice") or []
        if first.get("Status") != "Success" or not offices:
            raise PincodeError("No location found for this pincode")
        po = offices[0]
        return PincodeResult(
            pincode=pincode,
            city=(po.get("Name") or "").strip(),
            district=(po.get("District") or "").strip() or None,
            state=(po.get("State") or "").strip(),
        )
