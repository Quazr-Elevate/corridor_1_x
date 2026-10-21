"""Dev-mode provider — prints the mail and drops an .eml file in the outbox.

Lets the product boot with zero email credentials. Also keeps the last
messages in memory (``.sent``) so tests can assert on what was "sent".
Never raises on delivery.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from datetime import datetime, timezone
from email.message import EmailMessage as MimeMessage
from pathlib import Path

from app.integrations.email.base import EmailConfig, EmailMessage, EmailProvider

log = logging.getLogger("app.integrations.email.console")

_SAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(text: str, max_len: int = 40) -> str:
    return _SAFE_FILE_CHARS.sub("-", text.strip())[:max_len] or "unknown"


class ConsoleProvider(EmailProvider):
    name = "console"

    def __init__(self, config: EmailConfig) -> None:
        super().__init__(config)
        self.sent: deque[EmailMessage] = deque(maxlen=200)

    async def send(self, msg: EmailMessage) -> None:
        mime = self._build_mime(msg)
        try:
            path = await asyncio.to_thread(self._write_outbox, mime)
        except OSError as e:  # dev convenience only — never fail the caller
            log.warning("console email: could not write outbox: %s", e)
            path = None
        self.sent.append(msg)
        body = mime.get_body(preferencelist=("plain",))
        log.info(
            "email (console) to=%s subject=%r saved=%s\n%s",
            msg.to,
            msg.subject,
            path,
            body.get_content() if body is not None else "",
        )

    def _build_mime(self, msg: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = self.from_display
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        if self.config.reply_to:
            mime["Reply-To"] = self.config.reply_to
        mime.set_content(msg.text)
        mime.add_alternative(msg.html, subtype="html")
        return mime

    def _write_outbox(self, mime: MimeMessage) -> Path:
        self.config.outbox_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = self.config.outbox_dir / f"{stamp}_{_slug(str(mime['To']))}.eml"
        path.write_bytes(bytes(mime))
        return path
