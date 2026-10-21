"""Canonical forms used for uniqueness (backed by unique DB indexes).

Keep these in sync with the copies frozen inside
``alembic/versions/0018_hardening.py`` (migrations must not import app code).
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")


def normalize_phone(raw: str | None) -> str | None:
    """Keep digits and a '+' (spaces, dashes, parentheses dropped).
    '+91 98765 43210' and '+919876543210' collide."""
    if not raw:
        return None
    out = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return out or None


def normalize_legal_name(raw: str | None) -> str | None:
    """Lower-cased, trimmed, inner whitespace collapsed."""
    if not raw:
        return None
    out = _WS.sub(" ", raw.strip()).lower()
    return out or None


def normalize_website(raw: str | None) -> str | None:
    """'HTTPS://www.Kaveri.in/' → 'kaveri.in'; paths are kept
    ('facebook.com/acme'), query string / fragment dropped."""
    if not raw:
        return None
    s = raw.strip().lower()
    s = _SCHEME.sub("", s)
    s = s.split("#", 1)[0].split("?", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    return s or None
