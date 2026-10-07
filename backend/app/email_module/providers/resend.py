"""Resend.com adapter — the recommended production provider.

Docs: https://resend.com/docs/api-reference/emails/send-email

Only one HTTPS call: POST https://api.resend.com/emails with a bearer
token. Fast setup, generous free tier (3k/mo), modern API. The
``from`` must be a verified-domain address — Resend rejects anything
else — so if setup is incomplete you'll see 403s from here.
"""
from __future__ import annotations

import httpx

from ..config import EmailConfig
from .base import EmailMessage, EmailProvider


_RESEND_ENDPOINT = "https://api.resend.com/emails"


class ResendProvider(EmailProvider):
    name = "resend"

    def __init__(self, config: EmailConfig) -> None:
        if not config.api_key:
            raise RuntimeError(
                "EMAIL_PROVIDER=resend requires EMAIL_API_KEY to be set. "
                "Get one at https://resend.com/api-keys."
            )
        if not config.from_address:
            raise RuntimeError(
                "EMAIL_FROM must be set to a verified Resend sender address."
            )
        self.config = config

    def send(self, msg: EmailMessage) -> None:
        payload = {
            "from": (
                f"{self.config.from_name} <{self.config.from_address}>"
                if self.config.from_name
                else self.config.from_address
            ),
            "to": [msg.to],
            "subject": msg.subject,
            "html": msg.html,
            "text": msg.text,
        }
        if self.config.reply_to:
            payload["reply_to"] = self.config.reply_to

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.config.http_timeout_sec) as client:
            resp = client.post(_RESEND_ENDPOINT, headers=headers, json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Resend returned {resp.status_code}: {resp.text[:400]}"
            )
