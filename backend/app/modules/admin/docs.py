"""/admin/docs/* — KYB entry review, authenticated download and number reveal.

Every admin view of a KYB file or full number is written to
``admin_actions`` (``kyb.file_viewed`` / ``kyb.value_viewed``) — never the
value itself."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response

from app import notifications
from app.core.security import AdminEmail, parse_uuid
from app.models.business_document import DocStatus
from app.modules.admin import service
from app.modules.admin.schemas import DocRejectIn, DocStatusChanged, PendingDocRow
from app.modules.auth.deps import DbSession
from app.modules.verification import service as docs_service
from app.modules.verification.schemas import RevealedValue
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.files import file_response

router = APIRouter()

#: Caps bulk extraction through a compromised admin session.
ADMIN_REVEAL = RateLimitRule("admin.kyb_reveal:admin", limit=200, window_sec=60 * 60)


@router.get("/docs/pending", response_model=list[PendingDocRow], response_model_by_alias=True)
async def pending_docs(_: AdminEmail, db: DbSession) -> list[PendingDocRow]:
    return await service.pending_docs(db)


@router.get("/docs/{doc_id}/file")
async def download_doc(doc_id: str, admin: AdminEmail, db: DbSession) -> Response:
    await get_limiter().check(ADMIN_REVEAL, admin)
    doc = await docs_service.get_doc(db, parse_uuid(doc_id))
    data = await docs_service.read_doc_bytes(doc)
    service.record_action(
        db, admin_email=admin, action="kyb.file_viewed", target_type="business_document", target_id=doc.id,
        details={"business_id": str(doc.business_id), "doc_type": doc.doc_type},
    )
    await db.commit()
    return file_response(data, filename=doc.original_filename, cache_control="private, no-store")


@router.post("/docs/{doc_id}/reveal", response_model=RevealedValue, response_model_by_alias=True)
async def reveal_doc_value(doc_id: str, admin: AdminEmail, db: DbSession) -> RevealedValue:
    """Full number of a KYB entry (audited)."""
    await get_limiter().check(ADMIN_REVEAL, admin)
    doc = await docs_service.get_doc(db, parse_uuid(doc_id))
    value = docs_service.reveal_value(doc)
    service.record_action(
        db, admin_email=admin, action="kyb.value_viewed", target_type="business_document", target_id=doc.id,
        details={"business_id": str(doc.business_id), "doc_type": doc.doc_type},
    )
    await db.commit()
    return RevealedValue(id=str(doc.id), cert_type=doc.doc_type, value=value)


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
