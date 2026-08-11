"""Masters India GST Search API integration.

Dashboard: https://mastersindia.co
Docs: https://docs.mastersindia.co/gst-verification-api/

Auth: Bearer token from the Masters India dashboard, provided via
MASTERS_INDIA_ACCESS_TOKEN env var. If unset, a canned dev response is
returned so the API keeps working during local development.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas.gstin import Address, GstinLookup
from app.validators import GSTIN_REGEX

ENDPOINT = "https://commonapi.mastersindia.co/commonapis/searchgstin"

# First 2 digits of GSTIN encode the state — used as fallback if the
# provider omits or scrambles the state field.
STATE_BY_CODE: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}


async def lookup_gstin(gstin: str) -> GstinLookup:
    clean = gstin.strip().upper()
    if not GSTIN_REGEX.match(clean):
        raise ValueError("Enter a valid 15-character GSTIN")

    token = settings.masters_india_access_token
    if not token:
        return _stub(clean)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(
                ENDPOINT,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"gstin": clean},
            )
        except httpx.RequestError as e:
            raise ValueError("GSTIN lookup service is unreachable") from e

    if res.status_code in (401, 403):
        raise ValueError("GSTIN lookup credentials are invalid")
    if res.status_code >= 400:
        raise ValueError(f"GSTIN lookup failed ({res.status_code})")

    body = res.json()
    if body.get("error") or not body.get("data"):
        data = body.get("data") or {}
        raise ValueError(data.get("message") or body.get("message") or "GSTIN not found")

    data = body["data"]
    sts = data.get("sts")
    if sts and sts.lower() != "active":
        raise ValueError(f"This GSTIN is {sts}. Only active GSTINs can register.")

    return _map(data, clean)


def _map(data: dict, gstin: str) -> GstinLookup:
    addr = (data.get("pradr") or {}).get("addr") or {}
    building = ", ".join(
        p for p in [addr.get("bno"), addr.get("flno"), addr.get("bnm"), addr.get("st"), addr.get("loc")] if p
    )
    nba = data.get("nba") or []
    return GstinLookup(
        gstin=gstin,
        legal_name=data["lgnm"],
        trade_name=data.get("tradeNam"),
        pan=gstin[2:12],
        business_type=data.get("ctb") or "",
        nature_of_business=", ".join(nba) if nba else None,
        masked_mobile="",
        address=Address(
            building=building or None,
            city=addr.get("city") or "",
            district=addr.get("dst"),
            state=addr.get("stcd") or STATE_BY_CODE.get(gstin[:2]) or "",
            pincode=addr.get("pncd") or "",
        ),
    )


def _stub(gstin: str) -> GstinLookup:
    return GstinLookup(
        gstin=gstin,
        legal_name="Kaveri Foods Private Limited",
        trade_name="Kaveri Foods",
        pan=gstin[2:12],
        business_type="Private Limited Company",
        nature_of_business="Wholesale Business, Manufacturing",
        masked_mobile="",
        address=Address(
            building="Plot 14, MIDC Phase II",
            city="Nashik",
            district="Nashik",
            state=STATE_BY_CODE.get(gstin[:2]) or "Maharashtra",
            pincode="422007",
        ),
    )
