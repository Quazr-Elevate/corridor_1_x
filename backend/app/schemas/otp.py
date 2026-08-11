from typing import Literal

from app.schemas.base import CamelModel


class OtpSendRequest(CamelModel):
    channel: Literal["phone", "email"]
    value: str
    purpose: Literal["gstin", "phone"]


class OtpSendResponse(CamelModel):
    otp_id: str
    destination: str
    expires_in_sec: int
    dev_hint: str | None = None


class OtpVerifyRequest(CamelModel):
    otp_id: str
    code: str
    mobile: str


class OtpVerifyResponse(CamelModel):
    ok: bool
    error: str | None = None
