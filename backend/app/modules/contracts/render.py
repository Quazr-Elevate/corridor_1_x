"""Rendering a document, and the identity lint (CX-106).

Templates are plain text in a sandboxed Jinja environment: no HTML, no
attribute access beyond the context given, and an unknown variable is an
error rather than a blank. A rendered document that carries any identity of
the other side's company or people is refused before it is stored."""
from __future__ import annotations

import hashlib
import re

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import Conflict

_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
_SPACE = re.compile(r"\s+")


def render(template_body: str, context: dict) -> str:
    return _env.from_string(template_body).render(**context)


def sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def lint(body: str, forbidden: list[str]) -> None:
    """Refuse a document that names the other side. Compared case- and
    space-insensitively, so a reflowed line doesn't slip through."""
    flat = _SPACE.sub(" ", body).lower()
    if any(_SPACE.sub(" ", marker).lower() in flat for marker in forbidden):
        raise Conflict("This document would show the other side's identity, so it wasn't created. Check the terms and notes.")
