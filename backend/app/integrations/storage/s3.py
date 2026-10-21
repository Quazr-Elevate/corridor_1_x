"""S3 / Cloudflare R2 storage — skeleton.

Planned implementation (``aioboto3`` or ``aiobotocore``):

* ``save``   → ``put_object(Bucket, Key, Body, ContentType)``
* ``open``   → ``get_object(...)["Body"].read()`` (NoSuchKey → ObjectNotFound)
* ``delete`` → ``delete_object``
* ``exists`` → ``head_object`` (404 → False)

Settings: ``STORAGE_BACKEND=s3``, ``STORAGE_S3_BUCKET``, ``STORAGE_S3_REGION``,
``STORAGE_S3_ENDPOINT_URL`` (R2: ``https://<account>.r2.cloudflarestorage.com``),
``STORAGE_S3_ACCESS_KEY_ID``, ``STORAGE_S3_SECRET_ACCESS_KEY``.

Objects stay private; the app keeps serving them through its own routes
(auth for KYB docs, ``nosniff`` + correct Content-Type for photos), so the
public URL shape does not change when switching backends.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.integrations.storage.base import StorageProvider, StoredObject

_MSG = (
    "S3Storage is not implemented yet. Set STORAGE_BACKEND=local, or implement "
    "app/integrations/storage/s3.py (see module docstring)."
)


@dataclass(frozen=True)
class S3Config:
    bucket: str
    region: str = ""
    endpoint_url: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    prefix: str = ""


class S3Storage(StorageProvider):
    name = "s3"

    def __init__(self, config: S3Config) -> None:
        if not config.bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 requires STORAGE_S3_BUCKET.")
        self.config = config

    async def save(self, data: bytes, key: str, content_type: str) -> StoredObject:
        raise NotImplementedError(_MSG)

    async def open(self, key: str) -> bytes:
        raise NotImplementedError(_MSG)

    async def delete(self, key: str) -> None:
        raise NotImplementedError(_MSG)

    async def exists(self, key: str) -> bool:
        raise NotImplementedError(_MSG)
