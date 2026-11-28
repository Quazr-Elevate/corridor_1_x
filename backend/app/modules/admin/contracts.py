"""/admin/… — LOIs, contracts and their templates as the desk works them (A-081)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy import select

from app import notifications
from app.core.errors import NotFound
from app.core.security import ip_prefix, parse_uuid
from app.models.contract import ContractTemplate, DealDocument
from app.models.deal import Deal
from app.models.negotiation import TermSheet
from app.modules.admin import service as audit
from app.modules.admin.deps import CanApproveTemplates, CanSignDocuments, CanTriageRfqs
from app.modules.auth.deps import DbSession
from app.modules.contracts import documents, templates
from app.modules.contracts.schemas import (
    ApproveTemplateIn,
    DeskDocumentOut,
    DeskSignature,
    SignIn,
    TemplateOut,
    VoidIn,
)
from app.modules.negotiation import service
from app.modules.negotiation.router import _mail_side
from app.ratelimit.deps import client_ip
from app.shared.schemas import ItemList, item_list

router = APIRouter()


async def _desk_docs(db, deal: Deal, rows: list[DealDocument]) -> list[DeskDocumentOut]:
    signatures = await documents.signatures_of(db, [d.id for d in rows])
    out = []
    for d in rows:
        ts = await db.get(TermSheet, d.term_sheet_id)
        template = await db.get(ContractTemplate, d.template_id)
        out.append(DeskDocumentOut(
            id=str(d.id), deal_code=deal.code, kind=d.kind, side=d.side, status=d.status, body=d.body,
            content_sha256=d.content_sha256, value_minor=d.value_minor, currency=d.currency,
            term_sheet_version=ts.version, template=f"{template.code} v{template.version}", expires_at=d.expires_at,
            void_reason=d.void_reason, issued_at=d.issued_at, effective_at=d.effective_at,
            signatures=[DeskSignature(signer_type=s.signer_type, signer_role=s.signer_role, signed_at=s.signed_at)
                        for s in signatures[d.id]],
        ))
    return out


@router.get("/deals/{code}/documents", response_model=ItemList[DeskDocumentOut], response_model_by_alias=True)
async def deal_documents(code: str, _: CanTriageRfqs, db: DbSession) -> ItemList[DeskDocumentOut]:
    """Both sides' LOIs and contracts on the deal, newest first."""
    deal = await service.deal_by_code(db, code)
    rows = list(await db.scalars(
        select(DealDocument).where(DealDocument.deal_id == deal.id).order_by(DealDocument.issued_at.desc())
    ))
    return item_list(await _desk_docs(db, deal, rows))


@router.post("/deals/{code}/lois", response_model=ItemList[DeskDocumentOut], response_model_by_alias=True, status_code=201)
async def issue_lois(code: str, admin: CanTriageRfqs, db: DbSession, background: BackgroundTasks) -> ItemList[DeskDocumentOut]:
    """Issue the buy and sell LOIs from the agreed term sheet. Refused while a
    template waits for a lawyer, or if the two letters would disagree."""
    deal = await service.deal_by_code(db, code)
    docs = await documents.issue_lois(db, admin.id, deal)
    audit.record_action(db, admin=admin, action="lois.issued", target_type="deal", target_id=deal.id,
                        details={"deal": deal.code, "documents": [str(d.id) for d in docs]})
    await db.commit()
    for side in ("buyer", "seller"):
        await _mail_side(background, db, deal, side, notifications.send_document_to_sign)
    return item_list(await _desk_docs(db, deal, docs))


@router.post("/documents/{document_id}/countersign", response_model=DeskDocumentOut, response_model_by_alias=True)
async def countersign(
    document_id: str, payload: SignIn, admin: CanSignDocuments, db: DbSession, request: Request
) -> DeskDocumentOut:
    """Sign for Corridor One X after the party has signed."""
    s = await documents.countersign(
        db, admin.id, parse_uuid(document_id), payload.content_sha256, payload.signer_role,
        payload.authority_confirmed, ip_prefix(client_ip(request)),
    )
    audit.record_action(db, admin=admin, action="document.countersigned", target_type="deal_document",
                        target_id=s.document.id, details={"deal": s.deal.code, "kind": s.document.kind,
                                                          "sha256": s.document.content_sha256, "dealMoved": s.deal_moved})
    await db.commit()
    return (await _desk_docs(db, s.deal, [s.document]))[0]


@router.post("/documents/{document_id}/void", response_model=DeskDocumentOut, response_model_by_alias=True)
async def void_document(document_id: str, payload: VoidIn, admin: CanTriageRfqs, db: DbSession) -> DeskDocumentOut:
    """Void a document that isn't effective yet, with a reason both sides' records keep."""
    doc = await db.get(DealDocument, parse_uuid(document_id))
    if doc is None:
        raise NotFound("Document not found.")
    documents.void(doc, payload.reason)
    deal = await db.get(Deal, doc.deal_id)
    audit.record_action(db, admin=admin, action="document.voided", target_type="deal_document", target_id=doc.id,
                        reason=payload.reason, details={"deal": deal.code, "kind": doc.kind, "side": doc.side})
    await db.commit()
    return (await _desk_docs(db, deal, [doc]))[0]


@router.get("/contract-templates", response_model=ItemList[TemplateOut], response_model_by_alias=True)
async def list_templates(_: CanTriageRfqs, db: DbSession) -> ItemList[TemplateOut]:
    """Every template version, with whether a lawyer has approved it."""
    rows = await templates.all_versions(db)
    await db.commit()
    return item_list([TemplateOut(id=str(t.id), code=t.code, version=t.version, status=t.status, body=t.body,
                                  approval_note=t.approval_note, approved_at=t.approved_at) for t in rows])


@router.post("/contract-templates/{template_id}/approve", response_model=TemplateOut, response_model_by_alias=True)
async def approve_template(template_id: str, payload: ApproveTemplateIn, admin: CanApproveTemplates, db: DbSession) -> TemplateOut:
    """Record a lawyer's written approval of a draft version (super admin only)."""
    t = await templates.approve(db, admin.id, parse_uuid(template_id), payload.note)
    audit.record_action(db, admin=admin, action="template.approved", target_type="contract_template", target_id=t.id,
                        reason=payload.note, details={"code": t.code, "version": t.version})
    await db.commit()
    return TemplateOut(id=str(t.id), code=t.code, version=t.version, status=t.status, body=t.body,
                       approval_note=t.approval_note, approved_at=t.approved_at)
