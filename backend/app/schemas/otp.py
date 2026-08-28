from typing import Literal

from app.schemas.base import CamelModel


class OtpSendRequest(CamelModel):
    channel: Literal["phone", "email"]
    value: str  # phone (10 digits) or email
    purpose: Literal["gstin", "phone", "email", "signup", "signin"] = "phone"


class OtpSendResponse(CamelModel):
    otp_id: str
    destination: str
    expires_in_sec: int
    dev_hint: str | None = None


class OtpVerifyRequest(CamelModel):
    otp_id: str
    code: str
    channel: Literal["phone", "email"] = "phone"
    # One of these must be present depending on channel. Both optional so
    # existing callers (auth flow, GSTIN / PAN OTP) that only send `mobile`
    # continue to work.
    mobile: str | None = None
    email: str | None = None


class OtpVerifyResponse(CamelModel):
    ok: bool
    error: str | None = None
    # Populated on phone-channel verify. is_new=false means "this mobile is
    # already registered and the session cookie was just set"; is_new=true
    # means "no account yet — /auth/signup will consume the verified-phone
    # cookie to create it".
    is_new: bool | None = None
    user_id: str | None = None
