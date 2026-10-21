"""Brevo (ex-Sendinblue) adapter — https://developers.brevo.com/reference/sendtransacemail"""
from __future__ import annotations

import httpx

from app.integrations.email.base import EmailConfig, EmailMessage, EmailProvider
from app.integrations.email.providers._http import post_json

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class BrevoProvider(EmailProvider):
    name = "brevo"

    def __init__(self, config: EmailConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not config.api_key:
            raise RuntimeError("EMAIL_PROVIDER=brevo requires EMAIL_API_KEY.")
        if not config.from_address:
            raise RuntimeError("EMAIL_FROM must be set.")
        super().__init__(config)
        self._transport = transport

    async def send(self, msg: EmailMessage) -> None:
        sender: dict = {"email": self.config.from_address}
        if self.config.from_name:
            sender["name"] = self.config.from_name
        payload: dict = {
            "sender": sender,
            "to": [{"email": msg.to}],
            "subject": msg.subject,
            "htmlContent": msg.html,
            "textContent": msg.text,
        }
        if self.config.reply_to:
            payload["replyTo"] = {"email": self.config.reply_to}
        await post_json(
            self.config,
            url=BREVO_ENDPOINT,
            headers={"api-key": self.config.api_key, "accept": "application/json"},
            payload=payload,
            provider="brevo",
            transport=self._transport,
        )
