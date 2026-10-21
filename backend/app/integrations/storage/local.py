"""Local-filesystem storage rooted at an absolute directory.

On Railway, point ``STORAGE_DIR`` at a mounted volume (e.g. ``/data/uploads``)
— the container filesystem is ephemeral.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from app.integrations.storage.base import (
    InvalidKey,
    ObjectNotFound,
    StorageProvider,
    StoredObject,
    validate_key,
)


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("LocalStorage root must be an absolute path")
        self.root = root

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in path.parents:
            raise InvalidKey(f"key escapes storage root: {key!r}")
        return path

    async def save(self, data: bytes, key: str, content_type: str) -> StoredObject:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: temp file in the same dir, then rename.
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise

        await asyncio.to_thread(_write)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    async def open(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as e:
            raise ObjectNotFound(key) from e

    async def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(path.unlink, True)
        except OSError:
            pass

    async def exists(self, key: str) -> bool:
        try:
            path = self._path(key)
        except InvalidKey:
            return False
        return await asyncio.to_thread(path.is_file)
