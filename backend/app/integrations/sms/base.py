"""SMS provider interface — app-agnostic."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SmsConfig:
    provider: str = "console"
    outbox_dir: Path = Path("outbox/sms")
    default_country_code: str = "91"
    otp_length: int = 6
    otp_expiry_minutes: int = 10
    http_timeout_sec: float = 10.0
    max_attempts: int = 3
    # MSG91
    msg91_auth_key: str = ""
    msg91_otp_template_id: str = ""
    msg91_flow_template_id: str = ""
    msg91_flow_var_name: str = "message"
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OtpSendResult:
    to: str
    request_id: str | None = None


class SmsError(Exception):
    """Provider refused or failed to deliver."""


def normalize_msisdn(raw: str, default_country_code: str = "91") -> str:
    """Digits-only E.164 without '+', e.g. '+91 98765-43210' → '919876543210'.

    A bare 10-digit national number gets ``default_country_code`` prefixed;
    a leading national trunk '0' is dropped.
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("Phone number has no digits")
    if raw.strip().startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    return digits


class SmsProvider(ABC):
    name = "base"

    def __init__(self, config: SmsConfig) -> None:
        self.config = config

    def msisdn(self, to: str) -> str:
        return normalize_msisdn(to, self.config.default_country_code)

    @abstractmethod
    async def send_sms(self, to: str, text: str, *, variables: dict[str, str] | None = None) -> None:
        """Send a transactional SMS. Template-based providers (MSG91 flow /
        Indian DLT) put ``text`` into the configured template variable and
        merge ``variables``."""

    @abstractmethod
    async def send_otp(self, to: str) -> OtpSendResult:
        """Generate + deliver a one-time code (the provider owns the code)."""

    @abstractmethod
    async def verify_otp(self, to: str, code: str) -> bool:
        """True when ``code`` is the valid, unexpired OTP for ``to``."""
