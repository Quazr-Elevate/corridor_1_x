"""Safe file responses for user-uploaded content.

Content-Type comes from sniffing the bytes (never the stored filename or
the uploader's claimed type); anything that isn't a known-safe type is
served as an ``application/octet-stream`` attachment. ``nosniff`` stops
browsers from second-guessing.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import Response

from app.integrations.storage import DOCUMENT_TYPES, detect

_ASCII_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str | None, default: str = "file") -> str:
    """Basename only, control chars stripped, ≤ 200 chars."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:200] or default


def _disposition(kind: str, filename: str | None) -> str:
    if not filename:
        return kind
    ascii_name = _ASCII_SAFE.sub("_", filename) or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def file_response(data: bytes, *, filename: str | None = None, cache_control: str) -> Response:
    ftype = detect(data)
    if ftype is not None and ftype in DOCUMENT_TYPES:
        media_type, kind = ftype.mime, "inline"
    else:
        media_type, kind = "application/octet-stream", "attachment"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": _disposition(kind, filename),
            "Cache-Control": cache_control,
        },
    )
