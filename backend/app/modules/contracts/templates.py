"""Contract templates (CX-108). Version 1 of each is read from
``templates/<code>.txt`` on first use and starts as a draft; documents render
only from a version a super admin has approved with the lawyer's details."""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.time import utcnow
from app.models.contract import TEMPLATE_CODES, ContractTemplate

_DIR = Path(__file__).parent / "templates"
#: The codes built so far; the sales and purchase contracts come with CX-105.
AVAILABLE = tuple(c for c in TEMPLATE_CODES if (_DIR / f"{c}.txt").exists())


async def ensure_seeded(db: AsyncSession) -> None:
    """Add version 1 of every template file not yet in the table, as a draft."""
    have = set(await db.scalars(select(ContractTemplate.code)))
    for code in AVAILABLE:
        if code not in have:
            db.add(ContractTemplate(id=uuid.uuid4(), code=code, version=1, status="draft",
                                    body=(_DIR / f"{code}.txt").read_text(encoding="utf-8"), created_at=utcnow()))
    await db.flush()


async def all_versions(db: AsyncSession) -> list[ContractTemplate]:
    await ensure_seeded(db)
    return list(await db.scalars(select(ContractTemplate).order_by(ContractTemplate.code, ContractTemplate.version)))


async def approved(db: AsyncSession, code: str) -> ContractTemplate:
    """The newest approved version, or 409 while a lawyer hasn't approved one."""
    await ensure_seeded(db)
    template = await db.scalar(
        select(ContractTemplate).where(ContractTemplate.code == code, ContractTemplate.status == "approved")
        .order_by(ContractTemplate.version.desc()).limit(1)
    )
    if template is None:
        raise Conflict("This document's template is waiting for a lawyer's approval, so it can't be sent yet.")
    return template


async def approve(db: AsyncSession, admin_id: uuid.UUID, template_id: uuid.UUID | None, note: str) -> ContractTemplate:
    """Record the lawyer's approval of a draft version; it replaces any
    earlier approved version of the same template."""
    template = await db.get(ContractTemplate, template_id) if template_id else None
    if template is None:
        raise NotFound("Template not found.")
    if template.status != "draft":
        raise Conflict("Only a draft template can be approved.")
    for older in await db.scalars(select(ContractTemplate).where(
        ContractTemplate.code == template.code, ContractTemplate.status == "approved"
    )):
        older.status = "retired"
    template.status, template.approved_by, template.approved_at, template.approval_note = (
        "approved", admin_id, utcnow(), note,
    )
    return template
