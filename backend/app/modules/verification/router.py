"""KYB for the signed-in user's business.

* ``/kyb/document-types``       — the dropdown (admin-defined, per country)
* ``/me/verification-docs``     — KYB entries: add / list / change / delete,
  reveal the full number, download the file

Admin review endpoints live in :mod:`app.modules.admin.docs`."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from app.core.errors import BadRequest
from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.verification import rules, service
from app.modules.verification.schemas import (
    CountryOut,
    DocOut,
    DocTypeOut,
    RevealedValue,
    country_to_out,
    doc_to_out,
    doc_type_to_out,
)
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.files import file_response

router = APIRouter(prefix="/me/verification-docs", tags=["verification"])
types_router = APIRouter(prefix="/kyb", tags=["verification"])

#: Full KYB numbers are shown on deliberate action only; this caps bulk reads.
REVEAL_PER_USER = RateLimitRule("kyb.reveal:user", limit=30, window_sec=60 * 60)


async def _read(file: UploadFile | None) -> bytes | None:
    if file is None:
        return None
    return await file.read(service.MAX_DOC_BYTES + 1)


def _flag(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


@types_router.get("/countries", response_model=list[CountryOut], response_model_by_alias=True)
async def kyb_countries(_: CurrentUser, db: DbSession) -> list[CountryOut]:
    """Countries a business may pick — active and set up by admins with
    required documents — with their address labels."""
    return [country_to_out(c) for c in await rules.open_countries(db)]


@types_router.get("/document-types", response_model=list[DocTypeOut], response_model_by_alias=True)
async def document_types(user: CurrentUser, db: DbSession, country: str | None = Query(None, min_length=2, max_length=2)) -> list[DocTypeOut]:
    """Active document types for ``country`` (default: the business's)."""
    return [doc_type_to_out(t) for t in await service.list_types(db, country or user.business.country)]


@router.post("", response_model=DocOut, response_model_by_alias=True, status_code=201)
async def add_entry(
    user: CurrentUser,
    db: DbSession,
    document_type_id: str | None = Form(None, alias="documentTypeId"),
    custom_name: str | None = Form(None, alias="customName"),
    value: str | None = Form(None),
    file: UploadFile | None = File(None),
    cert_type: str | None = Form(None, alias="cert_type"),
) -> DocOut:
    """Add a KYB entry (multipart form).

    * ``documentTypeId`` — a type from ``/kyb/document-types``, **or**
      ``customName`` for "Other" (``cert_type`` is accepted as a legacy alias);
    * ``value`` and/or ``file`` — whatever the type requires.
    """
    if document_type_id and (custom_name or cert_type):
        raise BadRequest("Send either documentTypeId or customName, not both.")
    data = service.EntryInput(
        document_type_id=parse_uuid(document_type_id) if document_type_id else None,
        custom_name=custom_name if custom_name is not None else cert_type,
        value=value,
        filename=file.filename if file else None,
        content=await _read(file),
    )
    if data.document_type_id is None and document_type_id:
        raise BadRequest("Unknown document type.")
    doc = await service.add_entry(db, user, data)
    return doc_to_out(doc)


@router.get("", response_model=list[DocOut], response_model_by_alias=True)
async def list_entries(user: CurrentUser, db: DbSession) -> list[DocOut]:
    return [doc_to_out(d) for d in await service.list_docs(db, user.business_id)]


@router.patch("/{doc_id}", response_model=DocOut, response_model_by_alias=True)
async def update_entry(
    doc_id: str,
    user: CurrentUser,
    db: DbSession,
    custom_name: str | None = Form(None, alias="customName"),
    value: str | None = Form(None),
    file: UploadFile | None = File(None),
    remove_value: str | None = Form(None, alias="removeValue"),
    remove_file: str | None = Form(None, alias="removeFile"),
) -> DocOut:
    """Change an entry (multipart form): new ``value``, new ``file``,
    ``removeValue`` / ``removeFile``, or ``customName`` (Other only).
    The entry goes back to review."""
    data = service.EntryInput(
        custom_name=custom_name,
        value=value,
        filename=file.filename if file else None,
        content=await _read(file),
        remove_value=_flag(remove_value),
        remove_file=_flag(remove_file),
    )
    return doc_to_out(await service.update_entry(db, user, parse_uuid(doc_id), data))


@router.post("/{doc_id}/reveal", response_model=RevealedValue, response_model_by_alias=True)
async def reveal_entry(doc_id: str, user: CurrentUser, db: DbSession) -> RevealedValue:
    """The full number of one entry of the caller's own business."""
    await get_limiter().check(REVEAL_PER_USER, str(user.id))
    doc = await service.get_doc(db, parse_uuid(doc_id), business_id=user.business_id)
    return RevealedValue(id=str(doc.id), cert_type=doc.doc_type, value=service.reveal_value(doc))


@router.get("/{doc_id}/file")
async def download_doc(doc_id: str, user: CurrentUser, db: DbSession) -> Response:
    doc = await service.get_doc(db, parse_uuid(doc_id), business_id=user.business_id)
    data = await service.read_doc_bytes(doc)
    return file_response(data, filename=doc.original_filename, cache_control="private, no-store")


@router.delete("/{doc_id}", status_code=204, response_class=Response)
async def delete_doc(doc_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_doc(db, user, parse_uuid(doc_id))
    return Response(status_code=204)
