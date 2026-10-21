"""Object-storage interface — app-agnostic.

Keys are POSIX-style relative paths (``products/abc.jpg``). Providers must
reject keys that try to escape their root (``..``, absolute paths).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class StorageError(Exception):
    pass


class InvalidKey(StorageError):
    pass


class ObjectNotFound(StorageError):
    pass


def validate_key(key: str) -> str:
    """Return ``key`` if every segment is a plain, non-hidden name."""
    if not key or key.startswith("/") or "\\" in key:
        raise InvalidKey(f"invalid storage key: {key!r}")
    parts = key.split("/")
    if any(p in ("", ".", "..") or not _KEY_SEGMENT.match(p) for p in parts):
        raise InvalidKey(f"invalid storage key: {key!r}")
    return key


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    content_type: str


class StorageProvider(ABC):
    name = "base"

    @abstractmethod
    async def save(self, data: bytes, key: str, content_type: str) -> StoredObject: ...

    @abstractmethod
    async def open(self, key: str) -> bytes:
        """Return the object's bytes or raise :class:`ObjectNotFound`."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete ``key``; missing objects are not an error."""

    @abstractmethod
    async def exists(self, key: str) -> bool: ...
