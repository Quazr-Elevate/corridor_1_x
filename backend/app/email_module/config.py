"""Email module configuration — loaded from environment variables.

Kept intentionally free of any project-specific settings so this file
copies cleanly into another codebase. Callers that use their own
settings object can construct ``EmailConfig(...)`` directly instead of
``from_env()``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Project ships with an outbox folder beside the running process so the
# console provider's .eml files land somewhere obvious during dev. If
# the caller doesn't pass one, we fall back to <cwd>/outbox.
_DEFAULT_OUTBOX = Path("outbox")


@dataclass(frozen=True)
class EmailConfig:
    """Everything the module needs to send a message.

    ``provider`` picks the transport; ``api_key`` is the credential for
    hosted providers (ignored by the console provider). ``from_address``
    and ``from_name`` are what recipients see in their inbox.
    ``reply_to`` is optional — set it when your transactional sender
    (e.g. ``no-reply@…``) isn't where replies should land.
    """

    provider: str = "console"
    api_key: str = ""
    from_address: str = "no-reply@localhost"
    from_name: str = ""
    reply_to: str | None = None
    outbox_dir: Path = _DEFAULT_OUTBOX
    # Per-request HTTP timeout for hosted providers. Short enough that a
    # misbehaving upstream doesn't block the signup request forever;
    # long enough to tolerate normal transit.
    http_timeout_sec: float = 10.0

    @classmethod
    def from_env(cls, *, outbox_dir: Path | None = None) -> "EmailConfig":
        return cls(
            provider=(os.getenv("EMAIL_PROVIDER") or "console").strip().lower(),
            api_key=os.getenv("EMAIL_API_KEY", "").strip(),
            from_address=os.getenv("EMAIL_FROM", "no-reply@localhost").strip(),
            from_name=os.getenv("EMAIL_FROM_NAME", "").strip(),
            reply_to=(os.getenv("EMAIL_REPLY_TO") or "").strip() or None,
            outbox_dir=outbox_dir or _DEFAULT_OUTBOX,
        )

    def with_outbox(self, outbox_dir: Path) -> "EmailConfig":
        """Return a copy pointing at a different outbox directory.

        Useful for pinning the outbox under ``backend/`` regardless of
        where uvicorn was launched from.
        """
        return EmailConfig(
            provider=self.provider,
            api_key=self.api_key,
            from_address=self.from_address,
            from_name=self.from_name,
            reply_to=self.reply_to,
            outbox_dir=outbox_dir,
            http_timeout_sec=self.http_timeout_sec,
        )
