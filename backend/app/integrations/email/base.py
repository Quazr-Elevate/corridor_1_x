"""Shared types for every email provider adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmailConfig:
    """Everything the module needs to send mail (no app settings imported,
    so the package copies cleanly into another project)."""

    provider: str = "console"
    api_key: str = ""
    from_address: str = "no-reply@localhost"
    from_name: str = ""
    reply_to: str | None = None
    outbox_dir: Path = Path("outbox")
    http_timeout_sec: float = 10.0
    # Total tries for hosted providers on transient failures (network,
    # 429, 5xx). 4xx responses are never retried.
    max_attempts: int = 3


@dataclass(frozen=True)
class EmailMessage:
    """One outbound email. HTML + text are both carried — HTML-only mail is
    a soft spam signal, and the console provider prints the text part."""

    to: str
    subject: str
    html: str
    text: str


class EmailDeliveryError(Exception):
    """The provider refused or could not deliver the message."""


class EmailProvider(ABC):
    name: str = "base"

    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    @abstractmethod
    async def send(self, msg: EmailMessage) -> None:
        """Deliver ``msg`` or raise :class:`EmailDeliveryError`."""

    @property
    def from_display(self) -> str:
        c = self.config
        return f"{c.from_name} <{c.from_address}>" if c.from_name else c.from_address
