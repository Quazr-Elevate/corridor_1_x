"""Resend.com adapter — https://resend.com/docs/api-reference/emails/send-email

``from`` must be a verified-domain address, otherwise Resend answers 403.
"""
from __future__ import annotations

import httpx

from app.integrations.email.base import EmailConfig, EmailMessage, EmailProvider
from app.integrations.email.providers._http import post_json

RESEND_ENDPOINT = "https://api.resend.com/emails"


class ResendProvider(EmailProvider):
    name = "resend"

    def __init__(self, config: EmailConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not config.api_key:
            raise RuntimeError("EMAIL_PROVIDER=resend requires EMAIL_API_KEY.")
        if not config.from_address:
            raise RuntimeError("EMAIL_FROM must be a verified Resend sender address.")
        super().__init__(config)
        self._transport = transport

    async def send(self, msg: EmailMessage) -> None:
        payload: dict = {
            "from": self.from_display,
            "to": [msg.to],
            "subject": msg.subject,
            "html": msg.html,
            "text": msg.text,
        }
        if self.config.reply_to:
            payload["reply_to"] = self.config.reply_to
        await post_json(
            self.config,
            url=RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            payload=payload,
            provider="resend",
            transport=self._transport,
        )
