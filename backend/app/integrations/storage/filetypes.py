"""Content sniffing by magic bytes — never trust filename or Content-Type."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileType:
    kind: str  # "pdf" | "jpeg" | "png" | "webp"
    mime: str
    ext: str  # without the dot


PDF = FileType("pdf", "application/pdf", "pdf")
JPEG = FileType("jpeg", "image/jpeg", "jpg")
PNG = FileType("png", "image/png", "png")
WEBP = FileType("webp", "image/webp", "webp")

IMAGE_TYPES: frozenset[FileType] = frozenset({JPEG, PNG, WEBP})
DOCUMENT_TYPES: frozenset[FileType] = frozenset({PDF, JPEG, PNG, WEBP})

BY_EXT: dict[str, FileType] = {t.ext: t for t in (PDF, JPEG, PNG, WEBP)}


def detect(data: bytes) -> FileType | None:
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    return None
