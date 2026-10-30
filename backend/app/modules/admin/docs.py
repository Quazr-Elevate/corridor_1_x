"""/admin/docs/* — KYB document review + authenticated download."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app import notifications
from app.core.security import AdminEmail, parse_uuid
from app.models.business_document import DocStatus
from app.modules.admin import service
from app.modules.admin.schemas import DocRejectIn, DocStatusChanged, PendingDocRow
from app.modules.auth.deps import DbSession
from app.modules.verification import service as docs_service
from app.shared.files import file_response

router = APIRouter()


@router.get("/docs/pending", response_model=list[PendingDocRow], response_model_by_alias=True)
async def pending_docs(
    _: AdminEmail,
    db: DbSession,
    kind: str | None = Query(
        None,
        description="'business' for country-mandated slots, 'other' for custom uploads. Omit for both.",
    ),
) -> list[PendingDocRow]:
    return await service.pending_docs(db, kind=kind)


@router.get("/docs/{doc_id}/file")
async def download_doc(doc_id: str, _: AdminEmail, db: DbSession) -> Response:
    doc = await docs_service.get_doc(db, parse_uuid(doc_id))
    data = await docs_service.read_doc_bytes(doc)
    return file_response(data, filename=doc.original_filename, cache_control="private, no-store")


@router.post("/docs/{doc_id}/approve", response_model=DocStatusChanged, response_model_by_alias=True)
async def approve_doc(doc_id: str, admin: AdminEmail, db: DbSession) -> DocStatusChanged:
    d = await service.review_doc(db, admin, parse_uuid(doc_id), DocStatus.approved)
    return DocStatusChanged(doc_id=str(d.doc_id), status=d.status.value)


@router.post("/docs/{doc_id}/reject", response_model=DocStatusChanged, response_model_by_alias=True)
async def reject_doc(
    doc_id: str, payload: DocRejectIn, admin: AdminEmail, db: DbSession, background: BackgroundTasks
) -> DocStatusChanged:
    d = await service.review_doc(db, admin, parse_uuid(doc_id), DocStatus.rejected, reason=payload.reason)
    if d.owner_email:
        background.add_task(
            notifications.deliver_safely,
            notifications.send_doc_rejected,
            to=d.owner_email,
            first_name=notifications.first_name_of(d.owner_name),
            cert_type=d.cert_type,
            reason=payload.reason.strip(),
        )
    return DocStatusChanged(doc_id=str(d.doc_id), status=d.status.value)
