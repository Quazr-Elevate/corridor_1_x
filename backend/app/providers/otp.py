"""MSG91 OTP integration (SMS) plus an email OTP channel.

Phone dashboard: https://control.msg91.com
Docs: https://docs.msg91.com/otp

Auth: authkey header + template_id (the SMS template registered in your
MSG91 account with a `##OTP##` placeholder). Set MSG91_AUTH_KEY and
MSG91_TEMPLATE_ID in .env. Without them, we fall back to a stub that
accepts `123456` in dev.

Email channel is stubbed by default — real integration will bolt onto
SES / SendGrid / Postmark when we wire it up; interface stays the same.
"""

from __future__ import annotations

import time
from typing import Literal

import httpx

from app.config import settings
from app.schemas.otp import OtpSendResponse, OtpVerifyResponse
from app.validators import EMAIL_REGEX, PHONE_REGEX

SEND_URL = "https://control.msg91.com/api/v5/otp"
VERIFY_URL = "https://control.msg91.com/api/v5/otp/verify"
OTP_LENGTH = 6
OTP_EXPIRY_MIN = 5

Channel = Literal["phone", "email"]


def _pretty_phone(mobile: str) -> str:
    return f"+91 {mobile[:5]} {mobile[5:]}"


def _masked_email(email: str) -> str:
    """Cheap masking so we don't echo the full email back if not needed."""
    return email  # Return plain for now — form UX already knows what it typed


async def send_otp(channel: Channel, value: str) -> OtpSendResponse:
    clean = value.strip()
    if channel == "phone":
        return await _send_phone_otp(clean)
    if channel == "email":
        return await _send_email_otp(clean)
    raise ValueError(f"Unsupported OTP channel: {channel}")


async def verify_otp(channel: Channel, value: str, code: str) -> OtpVerifyResponse:
    if channel == "phone":
        return await _verify_phone_otp(value, code)
    if channel == "email":
        return await _verify_email_otp(value, code)
    return OtpVerifyResponse(ok=False, error=f"Unsupported OTP channel: {channel}")


# ── Phone (MSG91 or stub) ────────────────────────────────────────────────────


async def _send_phone_otp(mobile: str) -> OtpSendResponse:
    if not PHONE_REGEX.match(mobile):
        raise ValueError("Enter a valid 10-digit mobile number")

    key = settings.msg91_auth_key
    template = settings.msg91_template_id

    if not key or not template:
        return OtpSendResponse(
            otp_id=f"stub_p_{mobile}_{int(time.time())}",
            destination=_pretty_phone(mobile),
            expires_in_sec=OTP_EXPIRY_MIN * 60,
            dev_hint="Use 123456",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(
                SEND_URL,
                params={
                    "template_id": template,
                    "mobile": f"91{mobile}",
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
        destination=_pretty_phone(mobile),
        expires_in_sec=OTP_EXPIRY_MIN * 60,
    )


async def _verify_phone_otp(mobile: str, code: str) -> OtpVerifyResponse:
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


# ── Email (stub — swap for SES / SendGrid / Postmark later) ──────────────────


async def _send_email_otp(email: str) -> OtpSendResponse:
    if not EMAIL_REGEX.match(email):
        raise ValueError("Enter a valid email address")
    # No real email provider wired yet — return the stub with a dev hint
    return OtpSendResponse(
        otp_id=f"stub_e_{email}_{int(time.time())}",
        destination=_masked_email(email),
        expires_in_sec=OTP_EXPIRY_MIN * 60,
        dev_hint="Use 123456",
    )


async def _verify_email_otp(email: str, code: str) -> OtpVerifyResponse:
    # Same stub semantics as phone — accepts 123456 in dev
    if code == "123456":
        return OtpVerifyResponse(ok=True)
    return OtpVerifyResponse(ok=False, error="Incorrect code. Try again.")
