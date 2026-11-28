"""/deals/{code}/documents — a party's own LOIs and contracts (A-081)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.security import ip_prefix, parse_uuid
from app.models.contract import DealDocument
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.contracts import documents
from app.modules.contracts.schemas import DocumentOut, SignIn
from app.ratelimit.deps import client_ip
from app.shared.schemas import ItemList, item_list

router = APIRouter(prefix="/deals", tags=["deals"])


def document_out(doc: DealDocument, signatures: list) -> DocumentOut:
    by = {s.signer_type: s.signed_at for s in signatures}
    return DocumentOut(
        id=str(doc.id), kind=doc.kind, status=doc.status, body=doc.body, content_sha256=doc.content_sha256,
        value_minor=doc.value_minor, currency=doc.currency, expires_at=doc.expires_at, void_reason=doc.void_reason,
        issued_at=doc.issued_at, you_signed_at=by.get("party"), corridor_signed_at=by.get("corridor"),
        effective_at=doc.effective_at,
    )


@router.get("/{code}/documents", response_model=ItemList[DocumentOut], response_model_by_alias=True)
async def list_documents(code: str, user: CurrentUser, db: DbSession) -> ItemList[DocumentOut]:
    """Your own LOIs and contracts on this deal, newest first. The other side's are never shown."""
    _, _, rows = await documents.party_documents(db, user, code)
    signatures = await documents.signatures_of(db, [d.id for d in rows])
    return item_list([document_out(d, signatures[d.id]) for d in rows])


@router.post("/{code}/documents/{document_id}/sign", response_model=DocumentOut, response_model_by_alias=True)
async def sign_document(
    code: str, document_id: str, payload: SignIn, user: CurrentUser, db: DbSession, request: Request
) -> DocumentOut:
    """Sign the exact text you read, by its hash, confirming you may sign for
    your company. Corridor One X countersigns next."""
    s = await documents.sign_as_party(
        db, user, code, parse_uuid(document_id), payload.content_sha256, payload.signer_role,
        payload.authority_confirmed, ip_prefix(client_ip(request)),
    )
    await db.commit()
    return document_out(s.document, (await documents.signatures_of(db, [s.document.id]))[s.document.id])
