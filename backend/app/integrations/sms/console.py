"""Dev SMS provider — logs messages, writes them to the outbox, and keeps
OTPs in memory so ``verify_otp`` works end-to-end without a gateway."""
from __future__ import annotations

import asyncio
import hmac
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.integrations.sms.base import OtpSendResult, SmsConfig, SmsProvider

log = logging.getLogger("app.integrations.sms.console")


@dataclass(frozen=True)
class SentSms:
    to: str
    text: str


class ConsoleSmsProvider(SmsProvider):
    name = "console"
    MAX_VERIFY_ATTEMPTS = 5

    def __init__(self, config: SmsConfig) -> None:
        super().__init__(config)
        self.sent: deque[SentSms] = deque(maxlen=200)
        # msisdn -> (code, expires_at_monotonic, attempts)
        self._otps: dict[str, tuple[str, float, int]] = {}

    async def send_sms(self, to: str, text: str, *, variables: dict[str, str] | None = None) -> None:
        msisdn = self.msisdn(to)
        self.sent.append(SentSms(to=msisdn, text=text))
        try:
            path = await asyncio.to_thread(self._write_outbox, msisdn, text)
        except OSError as e:
            log.warning("console sms: could not write outbox: %s", e)
            path = None
        log.info("sms (console) to=%s saved=%s text=%r", msisdn, path, text)

    async def send_otp(self, to: str) -> OtpSendResult:
        msisdn = self.msisdn(to)
        code = "".join(secrets.choice("0123456789") for _ in range(self.config.otp_length))
        expires = time.monotonic() + self.config.otp_expiry_minutes * 60
        self._otps[msisdn] = (code, expires, 0)
        await self.send_sms(
            msisdn,
            f"{code} is your verification code. It expires in {self.config.otp_expiry_minutes} minutes.",
        )
        return OtpSendResult(to=msisdn, request_id=f"console-{secrets.token_hex(6)}")

    async def verify_otp(self, to: str, code: str) -> bool:
        msisdn = self.msisdn(to)
        entry = self._otps.get(msisdn)
        if entry is None:
            return False
        expected, expires, attempts = entry
        if time.monotonic() > expires or attempts >= self.MAX_VERIFY_ATTEMPTS:
            self._otps.pop(msisdn, None)
            return False
        if hmac.compare_digest(expected, code.strip()):
            self._otps.pop(msisdn, None)
            return True
        self._otps[msisdn] = (expected, expires, attempts + 1)
        return False

    def last_code_for(self, to: str) -> str | None:
        """Test helper — the pending OTP for ``to``."""
        entry = self._otps.get(self.msisdn(to))
        return entry[0] if entry else None

    def _write_outbox(self, msisdn: str, text: str) -> Path:
        self.config.outbox_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = self.config.outbox_dir / f"{stamp}_{msisdn}.txt"
        path.write_text(f"To: +{msisdn}\n\n{text}\n", encoding="utf-8")
        return path
