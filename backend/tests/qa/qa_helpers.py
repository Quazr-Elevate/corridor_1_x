"""Helpers for the QA flow suite (ported from Pegan's ``tests/qa`` on
``work/pegan-2026-10-21`` and adapted to main's API: ``kyb_document_types``,
country on the business profile, ``kyb:<code>`` / ``doc:<id>`` keys)."""
from __future__ import annotations

import uuid

import httpx

# A tiny valid 1x1 PNG — accepted wherever file bytes are expected.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6368606000000000050001a5a5a90a0000000049454e44ae426082"
)


def uniq(prefix: str) -> str:
    """Collision-free local part / code for one test."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def uniq_code(prefix: str) -> str:
    """A valid document-type code (lower-case letters, digits, underscore)."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def admin_add_doc_type(
    admin: httpx.AsyncClient,
    *,
    country: str = "IN",
    code: str,
    name: str,
    is_mandatory: bool = True,
    input_kind: str = "file",
) -> dict:
    """Add a document type to a country that is already set up."""
    r = await admin.post(
        "/admin/kyb/document-types",
        json={"country": country, "code": code, "name": name, "inputKind": input_kind, "isMandatory": is_mandatory},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def upload_entry(c: httpx.AsyncClient, *, type_id: str, filename: str = "cert.png") -> dict:
    """Add a KYB entry with a file for a document type."""
    r = await c.post(
        "/me/verification-docs",
        data={"documentTypeId": type_id},
        files={"file": (filename, TINY_PNG, "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def set_country(c: httpx.AsyncClient, country: str, *, name: str = "QA Trading Co") -> httpx.Response:
    """Save the business profile with ``country`` (country lives on the profile)."""
    return await c.put(
        "/me/business-profile",
        json={"legalName": f"{name} {uuid.uuid4().hex[:6]}", "country": country, "addressLine": "1 Test Road", "city": "Testville"},
    )


async def user_id_for(admin: httpx.AsyncClient, email: str) -> str:
    items = (await admin.get(f"/admin/users?q={email}")).json()["items"]
    hits = [i for i in items if i["email"] == email]
    assert hits, f"user not in admin list: {email}"
    return hits[0]["userId"]
