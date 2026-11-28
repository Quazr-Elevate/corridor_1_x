"""LOIs, contracts and their signatures (M4 · S9, CX-104, CX-105, A-081).

    issued ─(party signs)→ party_signed ─(Corridor One X countersigns)→ signed
    issued, party_signed ─(5 business days pass, or a newer term sheet)→ void

The desk issues a buy LOI and a sell LOI together, from the deal's agreed
term sheet. Both signed moves the deal to LOI_SIGNED; then the contracts
must be signed within five business days or everything lapses and the deal
returns to NEGOTIATING (A-081). A signature records the hash of the exact
text the signer read; a party's signer is identified by user, and their
name stays in the vault."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import add_business_days, ensure_aware, utcnow
from app.models.contract import DOCUMENT_LIVE, DealDocument, DocumentSignature
from app.models.deal import Deal, DealEvent, DealStatus
from app.models.negotiation import TermSheet
from app.models.user import User
from app.modules.contracts import mirror, render, templates
from app.modules.fx import service as fx
from app.modules.negotiation import counters
from app.modules.deals.machine import Actor, transition
from app.modules.masking import service as masking
from app.modules.negotiation import service as chat

SIGN_WITHIN_BUSINESS_DAYS = 5
PAYMENT_LABELS = {
    "advance": "advance payment",
    "lc_sight": "letter of credit at sight",
    "lc_usance": "usance letter of credit",
    "advance_balance_docs": "advance, balance against documents",
    "open_account": "open account",
}
#: Terms that must read the same in the buy and the sell document.
SHARED_TERMS = ("product", "quality", "packaging", "quantity", "unit", "incoterm", "port_of_loading",
                "destination_port", "delivery_from", "delivery_to", "notes", "term_sheet_version")


def _money(minor: int, currency: str) -> str:
    return f"{currency} {minor / 100:,.2f}"


def side_terms(ts: TermSheet, side: str) -> dict:
    """The term sheet as one side's document states it: shared terms, and
    that side's own price and payment terms only."""
    price, currency = getattr(ts, f"{side}_price_minor"), getattr(ts, f"{side}_currency")
    value = int(price * ts.quantity)
    return {
        "product": ts.product, "quality": ts.quality, "packaging": ts.packaging,
        "quantity": format(ts.quantity.normalize(), "f"), "unit": ts.unit, "incoterm": ts.incoterm,
        "port_of_loading": ts.port_of_loading, "destination_port": ts.destination_port,
        "delivery_from": ts.delivery_from.isoformat() if ts.delivery_from else None,
        "delivery_to": ts.delivery_to.isoformat() if ts.delivery_to else None,
        "notes": ts.notes, "term_sheet_version": ts.version,
        "price_minor": price, "currency": currency, "value_minor": value,
        "payment_terms": getattr(ts, f"{side}_payment_terms"),
    }


def check_consistent(buy: dict, sell: dict, ts: TermSheet) -> None:
    """Both documents state the term sheet's shared terms identically (CX-104)."""
    expected = side_terms(ts, "buyer")
    for term in SHARED_TERMS:
        if not (buy[term] == sell[term] == expected[term]):
            raise Conflict(f"The two letters disagree on {term.replace('_', ' ')}. Nothing was sent.")


async def _render_one(db: AsyncSession, deal: Deal, ts: TermSheet, side: str, code: str, terms: dict) -> tuple[str, object]:
    template = await templates.approved(db, code)
    party_id = deal.buyer_business_id if side == "buyer" else deal.seller_business_id
    other_id = deal.seller_business_id if side == "buyer" else deal.buyer_business_id
    window = " to ".join(x for x in (terms["delivery_from"], terms["delivery_to"]) if x) or None
    body = render.render(template.body, {
        "deal_code": deal.code, "template_code": template.code, "template_version": template.version,
        "template_draft": template.status != "approved",
        "corridor": {"legal_name": settings.corridor_legal_name, "address": settings.corridor_address},
        "party": await masking.party_for_document(db, party_id),
        "t": {**terms, "price": _money(terms["price_minor"], terms["currency"]),
              "value": _money(terms["value_minor"], terms["currency"]),
              "payment_terms": PAYMENT_LABELS.get(terms["payment_terms"], terms["payment_terms"]), "delivery": window},
        "term_sheet_version": ts.version, "term_sheet_ref": (ts.content_sha256 or "")[:12],
    })
    render.lint(body, await masking.identity_markers(db, other_id))
    return body, template


async def live_of(db: AsyncSession, deal: Deal, kind: str) -> dict[str, DealDocument]:
    rows = await db.scalars(select(DealDocument).where(
        DealDocument.deal_id == deal.id, DealDocument.kind == kind, DealDocument.status.in_(DOCUMENT_LIVE)
    ))
    return {d.side: d for d in rows}


async def issue_lois(db: AsyncSession, admin_id: uuid.UUID, deal: Deal) -> list[DealDocument]:
    """Render, check and send both LOIs from the agreed term sheet."""
    if deal.status != DealStatus.NEGOTIATING:
        raise Conflict("LOIs are issued while the deal is being negotiated.")
    ts = await db.scalar(select(TermSheet).where(TermSheet.deal_id == deal.id, TermSheet.status == "agreed"))
    if ts is None:
        raise Conflict("Both sides must agree a term sheet before the LOIs are issued.")
    if await live_of(db, deal, "loi"):
        raise Conflict("This deal already has LOIs out. Void them before issuing new ones.")
    buy, sell = side_terms(ts, "buyer"), side_terms(ts, "seller")
    check_consistent(buy, sell, ts)
    now = utcnow()
    expires = add_business_days(now, SIGN_WITHIN_BUSINESS_DAYS)
    docs = []
    for side, code, terms in (("buyer", "loi_buy", buy), ("seller", "loi_sell", sell)):
        body, template = await _render_one(db, deal, ts, side, code, terms)
        docs.append(DealDocument(
            id=uuid.uuid4(), deal_id=deal.id, kind="loi", side=side, term_sheet_id=ts.id, template_id=template.id,
            status="issued", body=body, content_sha256=render.sha256(body), terms=terms,
            value_minor=terms["value_minor"], currency=terms["currency"], expires_at=expires, issued_by=admin_id,
            issued_at=now,
        ))
    db.add_all(docs)
    return docs


# ── Contracts (CX-105, CX-109) ───────────────────────────────────────

CONTRACT_TERMS = ("tolerance_pct", "shipment_from", "shipment_to", "inspection_agency", "inspection_point",
                  "late_penalty_pct", "quality_penalty_pct", "claim_window_days", "governing_law", "seat",
                  "force_majeure")


def _plain(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return value


async def _over_legal_threshold(db: AsyncSession, value_minor: int, currency: str) -> bool:
    """Whether a contract's value, in USD, is above the legal-review threshold.
    An unknown rate counts as above: the safe side (CX-109)."""
    usd = fx.convert(Decimal(value_minor) / 100, currency, "USD", await fx.get_latest_rates(db))
    return usd is None or usd > settings.legal_review_threshold_usd


async def issue_contracts(
    db: AsyncSession, admin_id: uuid.UUID, deal: Deal, sales_in: dict, purchase_in: dict,
    legal_review_note: str | None,
) -> list[DealDocument]:
    """Render both contracts from the signed LOIs' term sheet and the desk's
    contract terms, refuse them unless they mirror, and send them."""
    if deal.status != DealStatus.LOI_SIGNED:
        raise Conflict("Contracts are issued once both LOIs are signed.")
    if await live_of(db, deal, "contract"):
        raise Conflict("This deal already has contracts out. Void them before issuing new ones.")
    lois = await live_of(db, deal, "loi")
    ts = await db.get(TermSheet, lois["buyer"].term_sheet_id)
    sales = {**side_terms(ts, "buyer"), **{k: _plain(sales_in[k]) for k in CONTRACT_TERMS}}
    purchase = {**side_terms(ts, "seller"), **{k: _plain(purchase_in[k]) for k in CONTRACT_TERMS}}
    sheet = await counters.sheet_of(db, deal)
    mirror.check(sales, purchase, purchase_to_sales_rate=sheet.fx_rate)
    if await _over_legal_threshold(db, sales["value_minor"], sales["currency"]) and not legal_review_note:
        raise Conflict(
            "This contract is above the legal-review threshold. Record who reviewed it before sending.",
            code="contract.legal_review",
        )
    signed_at = await _lois_signed_at(db, deal)
    expires = add_business_days(ensure_aware(signed_at), SIGN_WITHIN_BUSINESS_DAYS)
    now = utcnow()
    docs = []
    for side, code, terms in (("buyer", "sales", sales), ("seller", "purchase", purchase)):
        body, template = await _render_one(db, deal, ts, side, code, terms)
        docs.append(DealDocument(
            id=uuid.uuid4(), deal_id=deal.id, kind="contract", side=side, term_sheet_id=ts.id,
            template_id=template.id, status="issued", body=body, content_sha256=render.sha256(body), terms=terms,
            value_minor=terms["value_minor"], currency=terms["currency"], expires_at=expires, issued_by=admin_id,
            issued_at=now,
        ))
    db.add_all(docs)
    return docs


# ── Signing ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Signed:
    document: DealDocument
    deal: Deal
    #: The deal moved on because of this signature.
    deal_moved: bool = False


def _check_signable(doc: DealDocument, content_sha256: str, authority_confirmed: bool, expected: str) -> None:
    if doc.status != expected:
        raise Conflict("This document isn't waiting for this signature.")
    if ensure_aware(doc.expires_at) <= utcnow():
        raise Conflict("The time to sign this document has passed.")
    if content_sha256 != doc.content_sha256:
        raise Conflict("This document has changed since you opened it. Reload it and read it again.")
    if not authority_confirmed:
        raise BadRequest("Confirm that you are authorised to sign for your company.")


async def party_documents(db: AsyncSession, user: User, code: str) -> tuple[str, Deal, list[DealDocument]]:
    """This side's own documents only, newest first."""
    p = await chat.party(db, user, code)
    rows = list(await db.scalars(
        select(DealDocument).where(DealDocument.deal_id == p.deal.id, DealDocument.side == p.side)
        .order_by(DealDocument.issued_at.desc())
    ))
    return p.side, p.deal, rows


async def sign_as_party(
    db: AsyncSession, user: User, code: str, document_id: uuid.UUID | None, content_sha256: str, role: str,
    authority_confirmed: bool, ip_prefix: str | None,
) -> Signed:
    p = await chat.party(db, user, code)
    doc = await db.get(DealDocument, document_id) if document_id else None
    if doc is None or doc.deal_id != p.deal.id or doc.side != p.side:
        raise NotFound("Document not found.")
    chat.ensure_can_trade(user.business)
    _check_signable(doc, content_sha256, authority_confirmed, "issued")
    db.add(DocumentSignature(document_id=doc.id, signer_type="party", user_id=user.id, signer_role=role,
                             authority_confirmed=True, content_sha256=content_sha256, ip_prefix=ip_prefix,
                             signed_at=utcnow()))
    doc.status = "party_signed"
    return Signed(doc, p.deal)


async def countersign(
    db: AsyncSession, admin_id: uuid.UUID, document_id: uuid.UUID | None, content_sha256: str, role: str,
    authority_confirmed: bool, ip_prefix: str | None,
) -> Signed:
    """Corridor One X signs after the party. The second signed LOI moves the deal to LOI_SIGNED."""
    doc = await db.get(DealDocument, document_id) if document_id else None
    if doc is None:
        raise NotFound("Document not found.")
    deal = await db.get(Deal, doc.deal_id)
    _check_signable(doc, content_sha256, authority_confirmed, "party_signed")
    db.add(DocumentSignature(document_id=doc.id, signer_type="corridor", admin_id=admin_id, signer_role=role,
                             authority_confirmed=True, content_sha256=content_sha256, ip_prefix=ip_prefix,
                             signed_at=utcnow()))
    doc.status = "signed"
    await db.flush()
    both = await live_of(db, deal, doc.kind)
    moved = len(both) == 2 and all(d.status == "signed" for d in both.values())
    if moved and doc.kind == "loi":
        transition(db, deal, DealStatus.LOI_SIGNED, actor=Actor.admin(admin_id),
                   details={"lois": [str(d.id) for d in both.values()]})
    elif moved:
        # Both contracts take effect together, at one instant, in this one transaction (A-081).
        now = utcnow()
        for contract in both.values():
            contract.status, contract.effective_at = "effective", now
        transition(db, deal, DealStatus.CONTRACTED, actor=Actor.admin(admin_id),
                   details={"contracts": [str(d.id) for d in both.values()]})
    return Signed(doc, deal, moved)


async def signatures_of(db: AsyncSession, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DocumentSignature]]:
    out: dict[uuid.UUID, list[DocumentSignature]] = {i: [] for i in document_ids}
    if document_ids:
        for s in await db.scalars(select(DocumentSignature).where(DocumentSignature.document_id.in_(document_ids))):
            out[s.document_id].append(s)
    return out


# ── Voiding and lapse ────────────────────────────────────────────────


def void(doc: DealDocument, reason: str) -> None:
    if doc.status == "effective":
        raise Conflict("An effective contract can't be voided.")
    doc.status, doc.void_reason = "void", reason[:200]


async def void_built_on(db: AsyncSession, term_sheet_id: uuid.UUID) -> int:
    """A newer agreed term sheet voids the documents built on the old one (A-076)."""
    rows = list(await db.scalars(select(DealDocument).where(
        DealDocument.term_sheet_id == term_sheet_id, DealDocument.status.in_(("issued", "party_signed", "signed"))
    )))
    for doc in rows:
        void(doc, "A newer term sheet was agreed.")
    return len(rows)


async def _lois_signed_at(db: AsyncSession, deal: Deal) -> datetime | None:
    return await db.scalar(
        select(DealEvent.created_at).where(DealEvent.deal_id == deal.id, DealEvent.to_status == DealStatus.LOI_SIGNED)
        .order_by(DealEvent.created_at.desc()).limit(1)
    )


async def lapse_due(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Void every unsigned document past its time, and return deals whose
    contracts weren't signed within five business days of the LOIs to
    NEGOTIATING (A-081). Returns how many deals lapsed. The caller commits."""
    now = now or utcnow()
    lapsed: set[uuid.UUID] = set()
    for doc in list(await db.scalars(select(DealDocument).where(
        DealDocument.status.in_(("issued", "party_signed")), DealDocument.expires_at <= now
    ))):
        deal = await db.get(Deal, doc.deal_id)
        for sibling in (await live_of(db, deal, doc.kind)).values():
            if sibling.status != "effective":
                void(sibling, "Not signed in time.")
        lapsed.add(deal.id)
    for deal in list(await db.scalars(select(Deal).where(Deal.status == DealStatus.LOI_SIGNED))):
        signed_at = await _lois_signed_at(db, deal)
        if signed_at and add_business_days(ensure_aware(signed_at), SIGN_WITHIN_BUSINESS_DAYS) <= now:
            for kind in ("loi", "contract"):
                for doc in (await live_of(db, deal, kind)).values():
                    void(doc, "The contracts weren't signed in time.")
            transition(db, deal, DealStatus.NEGOTIATING, actor=Actor.system(), details={"reason": "contracts_not_signed"})
            lapsed.add(deal.id)
    return len(lapsed)
