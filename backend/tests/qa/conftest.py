"""QA-suite fixtures.

Reuses the project's existing test harness (`tests/conftest.py`) so these
tests run against the same throwaway-SQLite in-process app. Everything
here just adds helpers specific to the new flows.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

# Re-export the parent conftest's fixtures so pytest discovers them in this
# subdirectory too. (pytest auto-discovers from parent conftests, this is
# just a visible declaration.)
from tests.conftest import (  # noqa: F401
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    admin_client,
    client,
    code_from_email,
    fill_mandatory,
    make_client,
    set_status,
    signup_and_login,
)


def uniq(prefix: str) -> str:
    """Collision-free email local-part for a single test run."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


async def admin_add_requirement(
    admin: httpx.AsyncClient,
    *,
    country: str,
    slug: str,
    display_name: str,
    is_mandatory: bool = True,
) -> dict:
    """Create a doc requirement row and return it."""
    r = await admin.post(
        "/admin/doc-requirements",
        json={
            "countryCode": country,
            "slug": slug,
            "displayName": display_name,
            "isMandatory": is_mandatory,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# A tiny valid 1x1 PNG — the storage layer accepts it everywhere file
# bytes are expected (upload-photo, verification docs).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6368606000000000050001a5a5a90a0000000049454e44ae426082"
)


async def upload_slot_doc(
    c: httpx.AsyncClient, *, slot_id: str, slug: str, filename: str = "cert.png"
) -> dict:
    """Upload a tiny PNG against a given mandatory slot. Returns the DocOut."""
    r = await c.post(
        "/me/verification-docs",
        data={"cert_type": slug, "required_doc_type_id": slot_id},
        files={"file": (filename, TINY_PNG, "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def fill_profile_and_submit(
    c: httpx.AsyncClient, *, docs_to_upload: list[tuple[str, str]] | None = None
) -> dict:
    """Fill mandatory fields, upload each (slot_id, slug) in order, submit.
    Returns the submit-for-verification response."""
    await fill_mandatory(c)
    for slot_id, slug in docs_to_upload or []:
        await upload_slot_doc(c, slot_id=slot_id, slug=slug)
    r = await c.post("/me/submit-verification")
    assert r.status_code == 200, r.text
    return r.json()
