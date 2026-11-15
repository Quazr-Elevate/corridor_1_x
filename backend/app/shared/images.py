"""Uploaded images are re-encoded before they are stored.

A phone photo carries EXIF: GPS position, device, owner name, capture time.
On a platform that promises masked identities that is a direct leak, so the
stored file is rebuilt from the pixels alone. Only the colour profile is
kept, because dropping it changes how the picture looks.
"""
from __future__ import annotations

import asyncio
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import UnsupportedMediaType
from app.integrations.storage import IMAGE_TYPES, FileType

#: Refuse absurd dimensions before decoding (a small file can inflate to gigabytes).
MAX_PIXELS = 50_000_000

_FORMATS = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
_UNREADABLE = "This image could not be read. Export it again as JPG, PNG or WEBP and retry."


def _rebuild(content: bytes, ftype: FileType) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as src:
            if src.width * src.height > MAX_PIXELS:
                raise UnsupportedMediaType("This image is too large. Use one under 50 megapixels.")
            icc = src.info.get("icc_profile")
            # EXIF orientation goes away with the metadata; bake it into the pixels first.
            image = ImageOps.exif_transpose(src)
            image.load()
    except UnsupportedMediaType:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise UnsupportedMediaType(_UNREADABLE) from None

    if ftype.kind == "jpeg" and image.mode not in ("RGB", "L", "CMYK"):
        image = image.convert("RGB")
    # A fresh image holds the pixels and nothing else from the source file.
    clean = Image.new(image.mode, image.size)
    clean.paste(image)
    if image.mode == "P" and image.getpalette() is not None:
        clean.putpalette(image.getpalette())

    out = io.BytesIO()
    options: dict = {"icc_profile": icc} if icc else {}
    if ftype.kind == "jpeg":
        options.update(quality=90, optimize=True)
    elif ftype.kind == "png":
        options.update(optimize=True)
    else:
        options.update(quality=90)
    clean.save(out, format=_FORMATS[ftype.kind], **options)
    return out.getvalue()


async def strip_metadata(content: bytes, ftype: FileType) -> bytes:
    """The same picture with EXIF, XMP, GPS and comments removed. Files that
    are not images (PDF) pass through untouched."""
    if ftype not in IMAGE_TYPES:
        return content
    # Decoding and encoding are CPU work; keep them off the event loop.
    return await asyncio.to_thread(_rebuild, content, ftype)
