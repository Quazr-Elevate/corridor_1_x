from app.schemas.base import CamelModel


class AuthVerifyRequest(CamelModel):
    otp_id: str
    code: str
    mobile: str


class AuthVerifyResponse(CamelModel):
    user_id: str
    is_new: bool
    needs_profile: bool
