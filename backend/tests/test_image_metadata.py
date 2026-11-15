"""CX-067: every stored image is rebuilt without EXIF, XMP or GPS."""
from __future__ import annotations

import io

import pytest
from conftest import PDF_BYTES, signup_and_login
from PIL import Image
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.errors import UnsupportedMediaType
from app.integrations.storage import get_storage
from app.integrations.storage.filetypes import JPEG, PDF, PNG, WEBP
from app.models.business import Business
from app.models.business_document import BusinessDocument
from app.shared.images import strip_metadata

GPS_IFD = 0x8825
ORIENTATION = 0x0112
XMP = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description owner="Kaveri Foods"/></x:xmpmeta>'


def tagged_image(fmt: str = "JPEG", *, size: tuple[int, int] = (40, 20), orientation: int | None = None) -> bytes:
    """A small picture carrying GPS, camera and owner tags, like a phone photo."""
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    exif[0x0110] = "Phone 12"
    exif[0x013B] = "Kaveri Foods Pvt Ltd"
    if orientation:
        exif[ORIENTATION] = orientation
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (11.0, 0.0, 59.0), 3: "E", 4: (76.0, 57.0, 21.0)})
    out = io.BytesIO()
    image = Image.new("RGB", size, (200, 120, 40))
    image.putpixel((0, 0), (0, 0, 255))
    options = {"exif": exif}
    if fmt != "PNG":
        options["xmp"] = XMP
    image.save(out, format=fmt, **options)
    return out.getvalue()


def leaks(data: bytes) -> list[str]:
    """Identifying metadata still present in an image file."""
    found = []
    with Image.open(io.BytesIO(data)) as image:
        exif = image.getexif()
        if len(exif):
            found.append("exif")
        if exif.get_ifd(GPS_IFD):
            found.append("gps")
        if image.info.get("xmp") or image.info.get("XML:com.adobe.xmp"):
            found.append("xmp")
    for needle in (b"Kaveri Foods", b"PhoneMaker", b"xmpmeta"):
        if needle in data:
            found.append(needle.decode())
    return found


def test_the_fixture_really_carries_metadata():
    assert {"exif", "gps", "Kaveri Foods"} <= set(leaks(tagged_image("JPEG")))


@pytest.mark.parametrize(("fmt", "ftype"), [("JPEG", JPEG), ("PNG", PNG), ("WEBP", WEBP)])
async def test_strip_metadata_removes_everything_and_keeps_the_picture(fmt, ftype):
    clean = await strip_metadata(tagged_image(fmt), ftype)
    assert leaks(clean) == []
    with Image.open(io.BytesIO(clean)) as image:
        assert image.format == fmt and image.size == (40, 20)


async def test_orientation_is_baked_into_the_pixels():
    # Orientation 6 means "rotate 90° clockwise to display": 40x20 shows as 20x40.
    clean = await strip_metadata(tagged_image("JPEG", orientation=6), JPEG)
    with Image.open(io.BytesIO(clean)) as image:
        assert image.size == (20, 40) and ORIENTATION not in image.getexif()


async def test_pdfs_pass_through_and_broken_images_are_refused():
    assert await strip_metadata(PDF_BYTES, PDF) == PDF_BYTES
    with pytest.raises(UnsupportedMediaType):
        await strip_metadata(b"\xff\xd8\xff" + b"not really a jpeg", JPEG)


async def test_product_photo_is_stored_without_metadata(client):
    await signup_and_login(client, "exif1@kaverifoods.in")
    r = await client.post("/products/upload-photo", files={"file": ("lot.jpg", tagged_image("JPEG"), "image/jpeg")})
    assert r.status_code == 201, r.text
    served = await client.get(r.json()["url"])
    assert served.status_code == 200 and leaks(served.content) == []
    stored = await get_storage().open("products/" + r.json()["url"].rsplit("/", 1)[-1])
    assert leaks(stored) == []


async def test_kyb_image_is_stored_without_metadata(client):
    await signup_and_login(client, "exif2@kaverifoods.in")
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "GST Certificate"},
        files={"file": ("gst.jpg", tagged_image("JPEG"), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    async with SessionLocal() as db:
        doc = await db.scalar(select(BusinessDocument))
    stored = await get_storage().open(doc.storage_key)
    assert leaks(stored) == [] and doc.size_bytes == len(stored)
    assert leaks((await client.get(r.json()["url"])).content) == []


async def test_branding_image_is_stored_without_metadata(client):
    await signup_and_login(client, "exif3@kaverifoods.in")
    r = await client.post("/me/business/logo", files={"file": ("logo.webp", tagged_image("WEBP"), "image/webp")})
    assert r.status_code in (200, 201), r.text
    async with SessionLocal() as db:
        business = await db.scalar(select(Business))
    assert leaks(await get_storage().open(business.logo_key)) == []


async def test_a_file_that_only_looks_like_an_image_is_refused(client):
    await signup_and_login(client, "exif4@kaverifoods.in")
    r = await client.post("/products/upload-photo", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n<script>", "image/png")})
    assert r.status_code == 415 and r.json()["code"] == "request.unsupported_media_type"
