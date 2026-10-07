"""Dev-mode provider — prints the mail and drops an .eml file.

Lets the whole product boot with zero email credentials. Every signup,
verification, or notification lands in ``outbox/`` where the developer
can open the file in a mail client (double-click → Outlook / Mail /
Thunderbird) to see exactly what the recipient would get.

NEVER raises — the goal is for app code to be able to call
``send_email`` without a try/except in dev.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from email.message import EmailMessage as MimeMessage
from pathlib import Path

from ..config import EmailConfig
from .base import EmailMessage, EmailProvider


# On Windows the default stdout encoding is cp1252 — printing a
# soft-wrap character or any non-ascii body crashes the request. Fix it
# once per process so the first message never trips a dev who's
# running the backend in a cmd window.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


_SAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(text: str, max_len: int = 40) -> str:
    return _SAFE_FILE_CHARS.sub("-", text.strip())[:max_len] or "unknown"


class ConsoleProvider(EmailProvider):
    name = "console"

    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(self, msg: EmailMessage) -> None:
        mime = self._build_mime(msg)
        path = self._write_outbox(mime)
        self._log(mime, path)

    # ── internals ──

    def _build_mime(self, msg: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        from_display = (
            f"{self.config.from_name} <{self.config.from_address}>"
            if self.config.from_name
            else self.config.from_address
        )
        mime["From"] = from_display
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        if self.config.reply_to:
            mime["Reply-To"] = self.config.reply_to
        mime.set_content(msg.text)
        mime.add_alternative(msg.html, subtype="html")
        return mime

    def _write_outbox(self, mime: MimeMessage) -> Path:
        self.config.outbox_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        to = _slug(str(mime["To"]) or "unknown")
        path = self.config.outbox_dir / f"{stamp}_{to}.eml"
        path.write_bytes(bytes(mime))
        return path

    def _log(self, mime: MimeMessage, path: Path) -> None:
        sep = "-" * 60
        body = mime.get_body(preferencelist=("plain",))
        body_text = body.get_content() if body is not None else ""
        print(
            "\n"
            "=== OUTBOUND EMAIL " + "=" * 40 + "\n"
            f"  to      : {mime['To']}\n"
            f"  from    : {mime['From']}\n"
            f"  subject : {mime['Subject']}\n"
            f"  saved   : {path}\n"
            + sep + "\n"
            + body_text
            + "\n" + sep + "\n",
            flush=True,
        )
