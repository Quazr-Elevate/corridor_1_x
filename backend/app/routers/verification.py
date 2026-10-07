"""KYB document uploads — business registration, trade license, etc.

User-facing: upload / list / delete your own docs.
Admin-facing endpoints live in routers/admin.py (queue + download).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.verification_doc import VerificationDoc
from app.schemas.base import CamelModel

router = APIRouter(prefix="/me/verification-docs", tags=["verification"])

# 10 MB — big enough for a scanned PDF/photo, small enough that a wrong
# upload doesn't choke the server.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_ROOT = _BACKEND_DIR / "uploads" / "verification"


class DocOut(CamelModel):
    id: str
    cert_type: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    rejection_reason: str | None = None
    uploaded_at: datetime
    reviewed_at: datetime | None = None
    url: str


def _dto(doc: VerificationDoc) -> DocOut:
    return DocOut(
        id=str(doc.id),
        cert_type=doc.cert_type,
        filename=doc.filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        status=doc.status.value,
        rejection_reason=doc.rejection_reason,
        uploaded_at=doc.uploaded_at,
        reviewed_at=doc.reviewed_at,
        url=f"/uploads/verification/{doc.stored_path}",
    )


@router.post("", response_model=DocOut, response_model_by_alias=True, status_code=201)
async def upload_doc(
    cert_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocOut:
    cert_type = cert_type.strip()
    if not cert_type:
        raise HTTPException(
            status_code=400,
            detail="Pick a certificate type before uploading.",
        )
    if len(cert_type) > 150:
        raise HTTPException(
            status_code=400,
            detail="Certificate type is too long (150 chars max).",
        )

    if not file.content_type or not any(
        file.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES
    ):
        raise HTTPException(
            status_code=415,
            detail="Only PDFs and images (JPG / PNG) are accepted.",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Store under {user_id}/{unique}.{ext} so one user's docs don't clobber
    # another's and the original filename stays as metadata only.
    user_dir = UPLOAD_ROOT / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix.lower()
    disk_name = f"{uuid.uuid4().hex}{ext}"
    (user_dir / disk_name).write_bytes(content)

    doc = VerificationDoc(
        user_id=user.id,
        cert_type=cert_type,
        filename=file.filename or disk_name,
        stored_path=f"{user.id}/{disk_name}",
        mime_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _dto(doc)


@router.get("", response_model=list[DocOut], response_model_by_alias=True)
async def list_docs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocOut]:
    rows = await db.scalars(
        select(VerificationDoc)
        .where(VerificationDoc.user_id == user.id)
        .order_by(VerificationDoc.uploaded_at.desc())
    )
    return [_dto(d) for d in rows]


@router.delete("/{doc_id}", status_code=204, response_class=Response)
async def delete_doc(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        did = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Doc not found") from None

    doc = await db.get(VerificationDoc, did)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Doc not found")

    disk = UPLOAD_ROOT / doc.stored_path
    if disk.exists():
        try:
            disk.unlink()
        except OSError:
            # Best-effort — if the file is already gone (or locked on
            # Windows), still remove the DB row so the UI reflects the
            # user's intent.
            pass

    await db.delete(doc)
    await db.commit()
    return Response(status_code=204)
