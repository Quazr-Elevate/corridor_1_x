"""MSG91 OTP integration (SMS provider popular in India).

Dashboard: https://control.msg91.com
Docs: https://docs.msg91.com/otp

Auth: authkey header + template_id (the SMS template registered in your
MSG91 account with a `##OTP##` placeholder). Set MSG91_AUTH_KEY and
MSG91_TEMPLATE_ID in .env. Without them the provider falls back to a stub
that accepts `123456` in dev.
"""

from __future__ import annotations

import time

import httpx

from app.config import settings
from app.schemas.otp import OtpSendResponse, OtpVerifyResponse
from app.validators import PHONE_REGEX

SEND_URL = "https://control.msg91.com/api/v5/otp"
VERIFY_URL = "https://control.msg91.com/api/v5/otp/verify"
OTP_LENGTH = 6
OTP_EXPIRY_MIN = 5


def _pretty(mobile: str) -> str:
    return f"+91 {mobile[:5]} {mobile[5:]}"


async def send_otp(mobile: str) -> OtpSendResponse:
    clean = mobile.strip()
    if not PHONE_REGEX.match(clean):
        raise ValueError("Enter a valid 10-digit mobile number")

    key = settings.msg91_auth_key
    template = settings.msg91_template_id

    if not key or not template:
        return OtpSendResponse(
            otp_id=f"stub_{clean}_{int(time.time())}",
            destination=_pretty(clean),
            expires_in_sec=OTP_EXPIRY_MIN * 60,
            dev_hint="Use 123456",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(
                SEND_URL,
                params={
                    "template_id": template,
                    "mobile": f"91{clean}",
                    "authkey": key,
                    "otp_length": OTP_LENGTH,
                    "otp_expiry": OTP_EXPIRY_MIN,
                },
                json={},
            )
        except httpx.RequestError as e:
            raise ValueError("SMS service is unreachable") from e

    body = res.json() if res.content else {}
    if res.status_code >= 400 or body.get("type") != "success" or not body.get("request_id"):
        raise ValueError(body.get("message") or f"Could not send OTP ({res.status_code})")

    return OtpSendResponse(
        otp_id=f"msg91_{body['request_id']}",
        destination=_pretty(clean),
        expires_in_sec=OTP_EXPIRY_MIN * 60,
    )


async def verify_otp(mobile: str, code: str) -> OtpVerifyResponse:
    key = settings.msg91_auth_key

    if not key:
        if code == "123456":
            return OtpVerifyResponse(ok=True)
        return OtpVerifyResponse(ok=False, error="Incorrect code. Try again.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(
                VERIFY_URL,
                params={"mobile": f"91{mobile.strip()}", "otp": code},
                headers={"authkey": key},
            )
        except httpx.RequestError:
            return OtpVerifyResponse(ok=False, error="SMS service is unreachable")

    body = res.json() if res.content else {}
    if res.status_code == 200 and body.get("type") == "success":
        return OtpVerifyResponse(ok=True)
    return OtpVerifyResponse(ok=False, error=body.get("message") or "Incorrect code. Try again.")
