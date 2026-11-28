"""/admin/… — bank accounts and bank statements as finance works them
(CX-020, CX-112, A-083)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.core.crypto import mask
from app.core.security import parse_uuid
from app.models.banking import BankAccount, BankStatementMap
from app.models.business import Business
from app.modules.admin import service as audit
from app.modules.admin.deps import CanRevealBankAccounts, CanVerifyBankAccounts, CanViewFinance, CanWorkStatements
from app.modules.admin.schemas import AccessReasonIn
from app.modules.auth.deps import DbSession
from app.modules.banking import accounts, statements
from app.modules.banking.schemas import (
    DeskBankAccountOut,
    ImportOut,
    MatchIn,
    NoteIn,
    RevealedAccount,
    StatementLineOut,
    StatementMapIn,
    StatementMapOut,
)
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.schemas import ItemList, item_list

router = APIRouter()

#: Full account numbers, per finance manager.
BANK_REVEAL = RateLimitRule("admin.bank_reveal:admin", limit=50, window_sec=60 * 60)


async def _desk_account(db, a: BankAccount) -> DeskBankAccountOut:
    business = await db.get(Business, a.business_id)
    return DeskBankAccountOut(
        id=str(a.id), currency=a.currency, country=a.country, bank_name=a.bank_name, routing_code=a.routing_code,
        account_masked=mask(a.account_last4), status=a.status, rejected_reason=a.rejected_reason,
        created_at=a.created_at, company_code=business.company_code if business else None,
        verified_at=a.verified_at, cooling_off_until=a.cooling_off_until,
    )


@router.get("/bank-accounts/pending", response_model=ItemList[DeskBankAccountOut], response_model_by_alias=True)
async def pending_accounts(_: CanViewFinance, db: DbSession) -> ItemList[DeskBankAccountOut]:
    """Accounts waiting for verification, oldest first, by company code."""
    return item_list([await _desk_account(db, a) for a in await accounts.pending(db)])


@router.post("/bank-accounts/{account_id}/verify", response_model=DeskBankAccountOut, response_model_by_alias=True)
async def verify_account(account_id: str, payload: NoteIn, admin: CanVerifyBankAccounts, db: DbSession) -> DeskBankAccountOut:
    """Confirm the account, saying how it was checked. Its cooling-off starts now."""
    a = await accounts.verify(db, admin.id, parse_uuid(account_id), payload.note)
    audit.record_action(db, admin=admin, action="bank_account.verified", target_type="bank_account",
                        target_id=a.id, reason=payload.note, details={"business_id": str(a.business_id)})
    await db.commit()
    return await _desk_account(db, a)


@router.post("/bank-accounts/{account_id}/reject", response_model=DeskBankAccountOut, response_model_by_alias=True)
async def reject_account(account_id: str, payload: NoteIn, admin: CanVerifyBankAccounts, db: DbSession) -> DeskBankAccountOut:
    a = await accounts.reject(db, parse_uuid(account_id), payload.note)
    audit.record_action(db, admin=admin, action="bank_account.rejected", target_type="bank_account",
                        target_id=a.id, reason=payload.note, details={"business_id": str(a.business_id)})
    await db.commit()
    return await _desk_account(db, a)


@router.post("/bank-accounts/{account_id}/reveal", response_model=RevealedAccount, response_model_by_alias=True)
async def reveal_account(account_id: str, payload: AccessReasonIn, admin: CanRevealBankAccounts, db: DbSession) -> RevealedAccount:
    """The full number and holder, with a reason (rate-limited, audited)."""
    await get_limiter().check(BANK_REVEAL, str(admin.id))
    a, number, holder = await accounts.reveal(db, parse_uuid(account_id))
    audit.record_action(db, admin=admin, action="bank_account.revealed", target_type="bank_account",
                        target_id=a.id, reason=payload.reason, details={"business_id": str(a.business_id)})
    await db.commit()
    return RevealedAccount(id=str(a.id), account_number=number, holder_name=holder)


# ── Statements (CX-112) ──────────────────────────────────────────────


def _map_out(m: BankStatementMap) -> StatementMapOut:
    return StatementMapOut(id=str(m.id), name=m.name, columns=m.columns, date_format=m.date_format,
                           default_currency=m.default_currency)


@router.get("/statement-maps", response_model=ItemList[StatementMapOut], response_model_by_alias=True)
async def list_maps(_: CanWorkStatements, db: DbSession) -> ItemList[StatementMapOut]:
    return item_list([_map_out(m) for m in await db.scalars(select(BankStatementMap).order_by(BankStatementMap.name))])


@router.post("/statement-maps", response_model=StatementMapOut, response_model_by_alias=True, status_code=201)
async def create_map(payload: StatementMapIn, admin: CanWorkStatements, db: DbSession) -> StatementMapOut:
    """Save how one bank's CSV export reads."""
    m = await statements.create_map(db, admin.id, name=payload.name, columns=payload.columns,
                                    date_format=payload.date_format, default_currency=payload.default_currency)
    audit.record_action(db, admin=admin, action="statement_map.created", target_type="bank_statement_map",
                        target_id=m.id, details={"name": m.name})
    await db.commit()
    return _map_out(m)


@router.post("/statements", response_model=ImportOut, response_model_by_alias=True, status_code=201)
async def import_statement(
    admin: CanWorkStatements, db: DbSession, map_id: str = Form(..., alias="mapId"), file: UploadFile = File(...)
) -> ImportOut:
    """Import a CSV statement: new credits are kept and matched where the
    rules allow; the rest wait in the queue. The same file twice is refused."""
    content = await file.read(statements.MAX_BYTES + 1)
    result = await statements.import_csv(db, admin.id, parse_uuid(map_id), file.filename or "statement.csv", content)
    audit.record_action(db, admin=admin, action="statement.imported", target_type="bank_statement",
                        target_id=result.statement.id,
                        details={"new": result.new, "matched": result.matched, "debitsSkipped": result.debits_skipped})
    await db.commit()
    return ImportOut(statement_id=str(result.statement.id), lines_total=result.total, lines_new=result.new,
                     lines_matched=result.matched, debits_skipped=result.debits_skipped)


def _line_out(line) -> StatementLineOut:
    return StatementLineOut(id=str(line.id), booked_on=line.booked_on, amount_minor=line.amount_minor,
                            currency=line.currency, reference=line.reference,
                            payer_account_last4=line.payer_account_last4, status=line.status, note=line.note)


@router.get("/statement-lines/unmatched", response_model=ItemList[StatementLineOut], response_model_by_alias=True)
async def unmatched_lines(_: CanWorkStatements, db: DbSession) -> ItemList[StatementLineOut]:
    """Credits no rule could match, oldest first."""
    return item_list([_line_out(line) for line in await statements.queue(db)])


@router.post("/statement-lines/{line_id}/match", response_model=StatementLineOut, response_model_by_alias=True)
async def match_line(line_id: str, payload: MatchIn, admin: CanWorkStatements, db: DbSession) -> StatementLineOut:
    """Match a queued credit to a buyer's milestone by hand, with a note."""
    line, deal = await statements.match_by_hand(db, admin.id, parse_uuid(line_id), parse_uuid(payload.milestone_id),
                                                payload.note)
    audit.record_action(db, admin=admin, action="statement_line.matched", target_type="bank_statement_line",
                        target_id=line.id, reason=payload.note,
                        details={"deal": deal.code, "milestone": str(line.milestone_id)})
    await db.commit()
    return _line_out(line)


@router.post("/statement-lines/{line_id}/set-aside", response_model=StatementLineOut, response_model_by_alias=True)
async def set_aside_line(line_id: str, payload: NoteIn, admin: CanWorkStatements, db: DbSession) -> StatementLineOut:
    """Take a credit that isn't a trade receipt out of the queue, with why."""
    line = await statements.set_aside(db, parse_uuid(line_id), payload.note)
    audit.record_action(db, admin=admin, action="statement_line.set_aside", target_type="bank_statement_line",
                        target_id=line.id, reason=payload.note)
    await db.commit()
    return _line_out(line)
