from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.shared.schemas import CamelModel, text


def _bcrypt_limit(v: str) -> str:
    # bcrypt only uses the first 72 bytes (and bcrypt>=5 refuses more).
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password is too long (72 bytes max).")
    return v


# ── Signup (email code on one screen) ────────────────────────────────


class SignupCodeRequest(CamelModel):
    """POST /auth/signup/code — step 1: send a 6-digit code to a work email."""

    email: EmailStr


class SignupCodeResponse(CamelModel):
    email: str
    message: str = "We emailed you a 6-digit code."
    resend_in_sec: int
    expires_in_sec: int
    # Only with DEBUG=true (local dev) — never in production.
    dev_code: str | None = None


class SignupVerifyRequest(CamelModel):
    """POST /auth/signup/verify — step 2: prove inbox ownership."""

    email: EmailStr
    code: str = Field(min_length=1, max_length=12)


class SignupVerifyResponse(CamelModel):
    email: str
    verified: bool = True


class SignupCompleteRequest(CamelModel):
    """POST /auth/signup/complete — step 3: create business + owner.

    Sign-up asks only for the person, the company and a password; country,
    address and KYB live on the business profile (skippable)."""

    email: EmailStr
    full_name: text(100, 2)  # type: ignore[valid-type]
    company_name: text(200, 2)  # type: ignore[valid-type]
    # Optional — collected on the business profile; kept for older clients.
    position: text(120) | None = None  # type: ignore[valid-type]
    password: str = Field(min_length=8, max_length=200)
    accept_terms: bool

    @field_validator("full_name")
    @classmethod
    def _no_digits_in_name(cls, v: str) -> str:
        if any(ch.isdigit() for ch in v):
            raise ValueError("Full name shouldn't contain digits.")
        return v

    @field_validator("password")
    @classmethod
    def _password_len(cls, v: str) -> str:
        return _bcrypt_limit(v)

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Accept the Terms and Privacy Policy to create an account.")
        return v


# ── Login / sessions ─────────────────────────────────────────────────


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(max_length=200)


class LoginResponse(CamelModel):
    user_id: str
    business_id: str
    role: str
    email: str
    business_name: str | None = None


class ChangePasswordRequest(CamelModel):
    """POST /auth/change-password — rotation only (current password required)."""

    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def _password_len(cls, v: str) -> str:
        return _bcrypt_limit(v)


class OkResponse(CamelModel):
    ok: bool = True


class SessionInfo(CamelModel):
    user_id: str | None = None


# ── Password reset ───────────────────────────────────────────────────


class ForgotPasswordRequest(CamelModel):
    """POST /auth/password/forgot — always answers the same way."""

    email: EmailStr


class ForgotPasswordResponse(CamelModel):
    message: str = "If an account exists for this email, we sent a 6-digit code."
    expires_in_sec: int
    # Only with DEBUG=true (local dev) and only when a code was sent.
    dev_code: str | None = None


class ResetPasswordRequest(CamelModel):
    email: EmailStr
    code: str = Field(min_length=1, max_length=12)
    new_password: str = Field(min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def _password_len(cls, v: str) -> str:
        return _bcrypt_limit(v)


# ── Security overview (/auth/security) ───────────────────────────────


class DeviceOut(CamelModel):
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_prefix: str | None = None
    user_agent: str | None = None
    current: bool = True


class AuthEventOut(CamelModel):
    event: str
    created_at: datetime
    ip_prefix: str | None = None
    user_agent: str | None = None


class SecurityOverview(CamelModel):
    """The one signed-in device + recent sign-in activity."""

    device: DeviceOut | None = None
    recent: list[AuthEventOut]
    idle_timeout_minutes: int
    max_session_days: int
