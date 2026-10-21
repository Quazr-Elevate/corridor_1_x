"""Reusable object storage (local filesystem now, S3/R2 later).

    from app.integrations.storage import get_storage
    await get_storage().save(data, "products/abc.jpg", "image/jpeg")
"""
from __future__ import annotations

from app.integrations.storage.base import (
    InvalidKey,
    ObjectNotFound,
    StorageError,
    StorageProvider,
    StoredObject,
    validate_key,
)
from app.integrations.storage.filetypes import DOCUMENT_TYPES, IMAGE_TYPES, FileType, detect
from app.integrations.storage.local import LocalStorage
from app.integrations.storage.s3 import S3Config, S3Storage

_storage: StorageProvider | None = None


def configure_storage(provider: StorageProvider) -> None:
    global _storage
    _storage = provider


def get_storage() -> StorageProvider:
    if _storage is None:
        raise RuntimeError("Storage not configured — call configure_storage() at startup.")
    return _storage


__all__ = [
    "DOCUMENT_TYPES",
    "IMAGE_TYPES",
    "FileType",
    "InvalidKey",
    "LocalStorage",
    "ObjectNotFound",
    "S3Config",
    "S3Storage",
    "StorageError",
    "StorageProvider",
    "StoredObject",
    "configure_storage",
    "detect",
    "get_storage",
    "validate_key",
]
