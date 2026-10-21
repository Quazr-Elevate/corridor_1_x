"""Reusable SMS module (console / MSG91). Not wired to any endpoint yet.

    from app.integrations.sms import get_sms_provider
    sms = get_sms_provider()
    await sms.send_otp("+91 98765 43210")
    ok = await sms.verify_otp("+91 98765 43210", "123456")
"""
from __future__ import annotations

from app.integrations.sms.base import (
    OtpSendResult,
    SmsConfig,
    SmsError,
    SmsProvider,
    normalize_msisdn,
)
from app.integrations.sms.console import ConsoleSmsProvider
from app.integrations.sms.msg91 import Msg91SmsProvider

PROVIDERS: dict[str, type[SmsProvider]] = {
    "console": ConsoleSmsProvider,
    "msg91": Msg91SmsProvider,
}

_config: SmsConfig | None = None
_provider: SmsProvider | None = None


def build_sms_provider(config: SmsConfig) -> SmsProvider:
    cls = PROVIDERS.get(config.provider.strip().lower())
    if cls is None:
        raise ValueError(f"Unknown SMS_PROVIDER={config.provider!r}. Expected one of: {', '.join(sorted(PROVIDERS))}.")
    return cls(config)


def configure_sms(config: SmsConfig) -> None:
    global _config, _provider
    _config = config
    _provider = None


def get_sms_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = build_sms_provider(_config or SmsConfig())
    return _provider


__all__ = [
    "ConsoleSmsProvider",
    "Msg91SmsProvider",
    "OtpSendResult",
    "PROVIDERS",
    "SmsConfig",
    "SmsError",
    "SmsProvider",
    "build_sms_provider",
    "configure_sms",
    "get_sms_provider",
    "normalize_msisdn",
]
