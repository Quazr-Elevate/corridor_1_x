"""/me/verification-docs — the KYB documents of the signed-in user's business.
Admin review endpoints live in :mod:`app.modules.admin.docs`."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.verification import service
from app.modules.verification.schemas import DocOut, doc_to_out
from app.shared.files import file_response

router = APIRouter(prefix="/me/verification-docs", tags=["verification"])


@router.post("", response_model=DocOut, response_model_by_alias=True, status_code=201)
async def upload_doc(
    user: CurrentUser,
    db: DbSession,
    cert_type: str = Form(...),
    file: UploadFile = File(...),
) -> DocOut:
    content = await file.read(service.MAX_DOC_BYTES + 1)
    doc = await service.upload_doc(db, user, cert_type=cert_type, filename=file.filename, content=content)
    return doc_to_out(doc)


@router.get("", response_model=list[DocOut], response_model_by_alias=True)
async def list_docs(user: CurrentUser, db: DbSession) -> list[DocOut]:
    return [doc_to_out(d) for d in await service.list_docs(db, user.business_id)]


@router.get("/{doc_id}/file")
async def download_doc(doc_id: str, user: CurrentUser, db: DbSession) -> Response:
    doc = await service.get_doc(db, parse_uuid(doc_id), business_id=user.business_id)
    data = await service.read_doc_bytes(doc)
    return file_response(data, filename=doc.original_filename, cache_control="private, no-store")


@router.delete("/{doc_id}", status_code=204, response_class=Response)
async def delete_doc(doc_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_doc(db, user, parse_uuid(doc_id))
    return Response(status_code=204)
