"""Bank statements and payment matching (CX-112, A-083).

Finance uploads the AD bank's CSV export; a saved column map says which
column is which. Only credits are kept. A credit clears a buyer's payment
milestone when, and only when:

* its amount and currency equal the milestone's exactly;
* the payer's account is one of the buyer's verified accounts (matched by
  keyed hash, never by name);
* for an automatic match, its reference names the deal's code and exactly
  one open milestone of that deal has that amount.

Anything else waits in the finance queue; a person may match it by hand
(the same amount, currency and payer checks apply) or set it aside with a
reason. Nothing is ever allocated by guesswork. A statement line is the
bank's booked entry, which is what CLEARED means here."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import utcnow
from app.models.banking import BankStatement, BankStatementLine, BankStatementMap
from app.models.deal import Deal
from app.models.payment import PaymentMilestone
from app.modules.banking import accounts
from app.modules.ledger import service as ledger
from app.modules.ledger.service import Line

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
REQUIRED_COLUMNS = ("date", "amount", "reference", "payer_account")
_DEAL_CODE = re.compile(r"DL-\d{8}", re.IGNORECASE)


@dataclass(frozen=True)
class ImportResult:
    statement: BankStatement
    total: int
    new: int
    matched: int
    debits_skipped: int


def _amount_minor(raw: str) -> int:
    clean = (raw or "").replace(",", "").replace(" ", "").strip()
    try:
        value = Decimal(clean)
    except InvalidOperation:
        raise BadRequest(f"“{raw}” isn't an amount. Check the map's amount column.") from None
    if value != value.quantize(Decimal("0.01")):
        raise BadRequest(f"“{raw}” has more than two decimal places.")
    return int(value * 100)


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()


async def create_map(db: AsyncSession, admin_id: uuid.UUID, *, name: str, columns: dict, date_format: str,
                     default_currency: str) -> BankStatementMap:
    missing = [c for c in REQUIRED_COLUMNS if not (columns.get(c) or "").strip()]
    if missing:
        raise BadRequest(f"Name the statement's column for: {', '.join(missing)}.")
    try:
        datetime.now().strftime(date_format)
    except ValueError:
        raise BadRequest("That date format isn't valid. Use a pattern like %d/%m/%Y.") from None
    if await db.scalar(select(BankStatementMap.id).where(BankStatementMap.name == name.strip())):
        raise Conflict("A map with that name already exists.")
    m = BankStatementMap(id=uuid.uuid4(), name=name.strip(), columns={k: v.strip() for k, v in columns.items() if v},
                         date_format=date_format, default_currency=default_currency, created_by=admin_id,
                         created_at=utcnow())
    db.add(m)
    return m


async def import_csv(db: AsyncSession, admin_id: uuid.UUID, map_id: uuid.UUID | None, filename: str,
                     content: bytes) -> ImportResult:
    """Read one CSV export: keep each credit not seen before, then try to
    match each new line. The same file twice is refused."""
    if len(content) > MAX_BYTES:
        raise BadRequest("The statement is larger than 2 MB. Export a shorter period.")
    stmap = await db.get(BankStatementMap, map_id) if map_id else None
    if stmap is None:
        raise NotFound("Statement map not found.")
    digest = hashlib.sha256(content).hexdigest()
    if await db.scalar(select(BankStatement.id).where(BankStatement.content_sha256 == digest)):
        raise Conflict("This statement file has already been imported.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise BadRequest("The statement isn't UTF-8 text. Export it as CSV (UTF-8).") from None
    reader = csv.DictReader(io.StringIO(text))
    cols = stmap.columns
    absent = [cols[c] for c in REQUIRED_COLUMNS if cols[c] not in (reader.fieldnames or [])]
    if absent:
        raise BadRequest(f"The file has no column named {', '.join(absent)}. Check the map against the export.")

    statement = BankStatement(id=uuid.uuid4(), map_id=stmap.id, filename=filename[:200], content_sha256=digest,
                              uploaded_by=admin_id, uploaded_at=utcnow())
    db.add(statement)
    await db.flush()
    total = new = debits = 0
    fresh: list[BankStatementLine] = []
    for n, row in enumerate(reader, start=1):
        if n > MAX_ROWS:
            raise BadRequest(f"The statement has more than {MAX_ROWS} lines. Export a shorter period.")
        total += 1
        amount = _amount_minor(row[cols["amount"]])
        if amount <= 0:
            debits += 1
            continue
        try:
            booked = datetime.strptime(row[cols["date"]].strip(), stmap.date_format).date()
        except ValueError:
            raise BadRequest(f"Line {n}: “{row[cols['date']]}” doesn't match the date format {stmap.date_format}.") from None
        currency = (row.get(cols.get("currency", ""), "") or stmap.default_currency).strip().upper()
        reference = " ".join((row[cols["reference"]] or "").split())[:200]
        payer = accounts.normalise_account(row[cols["payer_account"]] or "")
        payer_hash = accounts.account_hashes(payer)[0] if payer else None
        fingerprint = _fingerprint(booked, amount, currency, reference, payer_hash or "")
        if await db.scalar(select(BankStatementLine.id).where(BankStatementLine.fingerprint == fingerprint)):
            continue  # already imported from an overlapping statement
        line = BankStatementLine(
            id=uuid.uuid4(), statement_id=statement.id, line_no=n, booked_on=booked, amount_minor=amount,
            currency=currency, reference=reference, payer_account_hash=payer_hash,
            payer_account_last4=payer[-4:] if payer else None, fingerprint=fingerprint, status="unmatched",
            created_at=utcnow(),
        )
        db.add(line)
        fresh.append(line)
        new += 1
    await db.flush()
    matched = 0
    for line in fresh:
        if await _auto_match(db, line):
            matched += 1
    statement.lines_total, statement.lines_new, statement.lines_matched = total, new, matched
    return ImportResult(statement, total, new, matched, debits)


async def _open_buyer_milestones(db: AsyncSession, deal_id: uuid.UUID) -> list[PaymentMilestone]:
    return list(await db.scalars(select(PaymentMilestone).where(
        PaymentMilestone.deal_id == deal_id, PaymentMilestone.leg == "buyer", PaymentMilestone.status == "open",
    )))


async def _auto_match(db: AsyncSession, line: BankStatementLine) -> bool:
    codes = {c.upper() for c in _DEAL_CODE.findall(line.reference)}
    if len(codes) != 1:
        return False
    deal = await db.scalar(select(Deal).where(Deal.code == codes.pop()))
    if deal is None:
        return False
    candidates = [m for m in await _open_buyer_milestones(db, deal.id)
                  if m.amount_minor == line.amount_minor and m.currency == line.currency]
    if len(candidates) != 1 or not await _payer_is_buyer(db, line, deal):
        return False
    await _clear(db, line, candidates[0], deal, source="auto", admin_id=None, note=None)
    return True


async def _payer_is_buyer(db: AsyncSession, line: BankStatementLine, deal: Deal) -> bool:
    return bool(line.payer_account_hash) and line.payer_account_hash in await accounts.verified_hashes_of(
        db, deal.buyer_business_id
    )


async def _clear(db: AsyncSession, line: BankStatementLine, milestone: PaymentMilestone, deal: Deal, *,
                 source: str, admin_id: uuid.UUID | None, note: str | None) -> None:
    now = utcnow()
    line.status, line.milestone_id, line.match_source = "matched", milestone.id, source
    line.matched_by, line.matched_at, line.note = admin_id, now, note
    milestone.status, milestone.cleared_at = "cleared", now
    await ledger.post(
        db, kind="buyer_receipt", memo=f"{deal.code}: {milestone.kind} received", deal_id=deal.id,
        idempotency_key=f"statement_line:{line.id}", reference=("statement_line", str(line.id)), admin_id=admin_id,
        lines=[Line("bank", line.amount_minor, line.currency), Line("buyer_receivable", -line.amount_minor, line.currency, "buyer")],
    )


async def match_by_hand(db: AsyncSession, admin_id: uuid.UUID, line_id: uuid.UUID | None,
                        milestone_id: uuid.UUID | None, note: str) -> tuple[BankStatementLine, Deal]:
    """Finance matches a queued line to a milestone. The money rules still
    hold: the same amount and currency, from the buyer's verified account."""
    line = await db.get(BankStatementLine, line_id) if line_id else None
    if line is None:
        raise NotFound("Statement line not found.")
    if line.status != "unmatched":
        raise Conflict("This line has already been matched or set aside.")
    milestone = await db.get(PaymentMilestone, milestone_id) if milestone_id else None
    if milestone is None or milestone.leg != "buyer":
        raise NotFound("Payment milestone not found.")
    if milestone.status != "open":
        raise Conflict("That milestone has already been paid.")
    if (milestone.amount_minor, milestone.currency) != (line.amount_minor, line.currency):
        raise Conflict("The amount or currency differs from the milestone. Part payments aren't matched; ask the buyer to pay the full amount.")
    deal = await db.get(Deal, milestone.deal_id)
    if not await _payer_is_buyer(db, line, deal):
        raise Conflict("The money didn't come from one of the buyer's verified accounts, so it can't clear this milestone.")
    await _clear(db, line, milestone, deal, source="manual", admin_id=admin_id, note=note)
    return line, deal


async def set_aside(db: AsyncSession, line_id: uuid.UUID | None, reason: str) -> BankStatementLine:
    """A line that isn't a trade receipt (a refund, a fee credit), with why."""
    line = await db.get(BankStatementLine, line_id) if line_id else None
    if line is None:
        raise NotFound("Statement line not found.")
    if line.status != "unmatched":
        raise Conflict("This line has already been matched or set aside.")
    line.status, line.note = "ignored", reason
    return line


async def queue(db: AsyncSession) -> list[BankStatementLine]:
    return list(await db.scalars(
        select(BankStatementLine).where(BankStatementLine.status == "unmatched").order_by(BankStatementLine.booked_on)
    ))
