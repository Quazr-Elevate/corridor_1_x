from app.schemas.base import CamelModel


class SignupRequest(CamelModel):
    """POST /auth/signup — completes account creation after phone OTP.

    The mobile isn't in the payload; it comes from the cor1x_verified_phone
    cookie that /otp/verify set. Consent must be true (DPDP / UAE PDPL).
    """

    full_name: str
    email: str
    consent: bool
    # Frontend can pin the specific policy version the user agreed to so we
    # have a durable audit trail if we change the docs.
    consent_version: str | None = None


class SignupResponse(CamelModel):
    user_id: str
    is_new: bool = True


# Kept for BC — the frontend still imports these from the old /auth/verify
# stub. New signups don't use them; can be removed once the pulled UI is
# fully migrated to the cookie flow.
class AuthVerifyRequest(CamelModel):
    otp_id: str
    code: str
    mobile: str


class AuthVerifyResponse(CamelModel):
    user_id: str
    is_new: bool
    needs_profile: bool
