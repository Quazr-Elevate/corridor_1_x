"""MSG91 adapter (https://docs.msg91.com).

Endpoints used (all authenticate with the ``authkey`` header):

* Send OTP   — ``POST https://control.msg91.com/api/v5/otp``
               query: ``template_id``, ``mobile`` (country code + number,
               digits only), ``otp_length``, ``otp_expiry`` (minutes).
               MSG91 generates the code. Response
               ``{"type": "success", "request_id": "..."}``.
* Verify OTP — ``GET https://control.msg91.com/api/v5/otp/verify``
               query: ``otp``, ``mobile``. Response ``{"type": "success"}``
               or ``{"type": "error", "message": "..."}``.
* Transactional SMS (Flow) — ``POST https://control.msg91.com/api/v5/flow``
               body: ``{"template_id": ..., "short_url": "0",
               "recipients": [{"mobiles": "91XXXXXXXXXX", "<var>": "..."}]}``.
               Indian DLT rules require a pre-approved template; ``text`` is
               passed as the variable named by ``msg91_flow_var_name``.

Settings: ``SMS_MSG91_AUTH_KEY``, ``SMS_MSG91_OTP_TEMPLATE_ID``,
``SMS_MSG91_FLOW_TEMPLATE_ID``, ``SMS_MSG91_FLOW_VAR_NAME``.
"""
from __future__ import annotations

import httpx

from app.integrations._retry import TransientError, retry_async
from app.integrations.sms.base import OtpSendResult, SmsConfig, SmsError, SmsProvider

BASE_URL = "https://control.msg91.com/api/v5"


class Msg91SmsProvider(SmsProvider):
    name = "msg91"

    def __init__(self, config: SmsConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not config.msg91_auth_key:
            raise RuntimeError("SMS_PROVIDER=msg91 requires SMS_MSG91_AUTH_KEY.")
        super().__init__(config)
        self._transport = transport

    async def _request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict:
        headers = {"authkey": self.config.msg91_auth_key, "accept": "application/json"}

        async def _once() -> dict:
            try:
                async with httpx.AsyncClient(
                    base_url=BASE_URL, timeout=self.config.http_timeout_sec, transport=self._transport
                ) as client:
                    resp = await client.request(method, path, params=params, json=json, headers=headers)
            except httpx.HTTPError as e:
                raise TransientError(f"msg91 unreachable: {e}") from e
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientError(f"msg91 returned {resp.status_code}")
            try:
                data = resp.json()
            except ValueError:
                data = {"type": "error", "message": resp.text[:200]}
            if resp.status_code >= 300:
                raise SmsError(f"msg91 returned {resp.status_code}: {data}")
            return data if isinstance(data, dict) else {"type": "error", "message": str(data)}

        try:
            return await retry_async(_once, attempts=self.config.max_attempts, label="sms:msg91")
        except TransientError as e:
            raise SmsError(str(e)) from e

    async def send_sms(self, to: str, text: str, *, variables: dict[str, str] | None = None) -> None:
        if not self.config.msg91_flow_template_id:
            raise RuntimeError("SMS_MSG91_FLOW_TEMPLATE_ID is required for transactional SMS.")
        recipient = {"mobiles": self.msisdn(to), self.config.msg91_flow_var_name: text, **(variables or {})}
        data = await self._request(
            "POST",
            "/flow",
            json={"template_id": self.config.msg91_flow_template_id, "short_url": "0", "recipients": [recipient]},
        )
        if data.get("type") != "success":
            raise SmsError(f"msg91 flow failed: {data.get('message')}")

    async def send_otp(self, to: str) -> OtpSendResult:
        if not self.config.msg91_otp_template_id:
            raise RuntimeError("SMS_MSG91_OTP_TEMPLATE_ID is required to send OTPs.")
        msisdn = self.msisdn(to)
        data = await self._request(
            "POST",
            "/otp",
            params={
                "template_id": self.config.msg91_otp_template_id,
                "mobile": msisdn,
                "otp_length": self.config.otp_length,
                "otp_expiry": self.config.otp_expiry_minutes,
            },
        )
        if data.get("type") != "success":
            raise SmsError(f"msg91 send OTP failed: {data.get('message')}")
        return OtpSendResult(to=msisdn, request_id=data.get("request_id"))

    async def verify_otp(self, to: str, code: str) -> bool:
        data = await self._request(
            "GET", "/otp/verify", params={"otp": code.strip(), "mobile": self.msisdn(to)}
        )
        return data.get("type") == "success"
