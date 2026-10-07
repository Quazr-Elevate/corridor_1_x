from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class SignupRequest(CamelModel):
    """POST /auth/signup — email-only signup.

    No password here — the backend generates a temp one and emails it.
    The user types that temp password at the login screen (or clicks
    the magic link in the same mail) and is then forced to set a real
    password inside the portal.
    """

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    country_of_residence: str = Field(min_length=2, max_length=60)


class SignupResponse(CamelModel):
    """Echo the address for the 'check your inbox' popup.

    In dev mode (``settings.debug=True``), also returns ``dev_temp_password``
    + ``dev_magic_url`` so the frontend doesn't need to open the .eml file
    to run the flow. Never set in production.
    """

    email: str
    message: str = "Check your inbox for your temporary password."
    dev_temp_password: str | None = None
    dev_magic_url: str | None = None


class ResendSignupRequest(CamelModel):
    """POST /auth/signup/resend — issue a fresh temp credential.

    Invalidates the previous one. Rate-limited by email at the handler.
    """

    email: EmailStr


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class LoginResponse(CamelModel):
    user_id: str
    email: str
    business_name: str | None = None
    # True when the login used the temp credential — the frontend must
    # route the user to /dashboard/settings/password and lock everything
    # else behind it.
    must_change_password: bool = False


class ChangePasswordRequest(CamelModel):
    """POST /auth/change-password — set or rotate a real password.

    ``current_password`` is required only when the user already has a
    real password (rotation). On first-time setup — the session was
    issued via a temp credential — the backend ignores it, so the
    frontend can send an empty string. Keeping the field present in
    both modes keeps the TypeScript type simple.
    """

    current_password: str = Field(default="", max_length=200)
    new_password: str = Field(min_length=8, max_length=200)
