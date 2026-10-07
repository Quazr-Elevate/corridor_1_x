"""Brevo (formerly Sendinblue) adapter — fallback / higher-daily-cap.

Docs: https://developers.brevo.com/reference/sendtransacemail

More headroom on the free tier (300/day vs Resend's 100/day), bulkier
JSON schema. Useful when you expect >100/day on launch day.
"""
from __future__ import annotations

import httpx

from ..config import EmailConfig
from .base import EmailMessage, EmailProvider


_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class BrevoProvider(EmailProvider):
    name = "brevo"

    def __init__(self, config: EmailConfig) -> None:
        if not config.api_key:
            raise RuntimeError(
                "EMAIL_PROVIDER=brevo requires EMAIL_API_KEY to be set."
            )
        if not config.from_address:
            raise RuntimeError("EMAIL_FROM must be set.")
        self.config = config

    def send(self, msg: EmailMessage) -> None:
        payload = {
            "sender": {
                "email": self.config.from_address,
                **({"name": self.config.from_name} if self.config.from_name else {}),
            },
            "to": [{"email": msg.to}],
            "subject": msg.subject,
            "htmlContent": msg.html,
            "textContent": msg.text,
        }
        if self.config.reply_to:
            payload["replyTo"] = {"email": self.config.reply_to}

        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        with httpx.Client(timeout=self.config.http_timeout_sec) as client:
            resp = client.post(_BREVO_ENDPOINT, headers=headers, json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Brevo returned {resp.status_code}: {resp.text[:400]}"
            )
