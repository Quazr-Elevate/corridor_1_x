"""Shared types for every email provider adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """One outbound email, in the shape every provider accepts.

    ``html`` and ``text`` are both carried — HTML-only mail is a soft
    spam signal. The text version is also what the console provider
    renders to stdout so a developer can read the mail without opening
    the .eml file.
    """

    to: str
    subject: str
    html: str
    text: str


class EmailProvider(ABC):
    """A transport that can deliver one ``EmailMessage``.

    Implementations should raise on hard failures — the caller decides
    whether to swallow (console provider never raises) or surface
    (hosted providers raise so signups can retry).
    """

    name: str = "base"

    @abstractmethod
    def send(self, msg: EmailMessage) -> None: ...
