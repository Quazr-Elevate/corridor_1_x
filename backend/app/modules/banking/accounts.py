"""Business bank accounts (CX-020, A-083).

Stored like KYB numbers: encrypted at rest, a keyed hash for matching, the
last four for display; the full number and holder only through an audited,
rate-limited reveal. Finance verifies an account; payouts to it wait out the
cooling-off period. Adding an account for a currency retires the old one, so
a changed account is always re-verified and its cooling-off starts again."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.models.banking import BankAccount
from app.models.user import User
from app.modules.rfq import seed
from app.modules.rfq import service as settings_source

HASH_SCOPE = "bank_account"
_ACCOUNT = re.compile(r"^[A-Z0-9]{6,34}$")
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_SWIFT = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def normalise_account(raw: str) -> str:
    """Account numbers and IBANs compare without spaces or dashes, upper case."""
    return re.sub(r"[\s\-]", "", raw or "").upper()


def account_hashes(raw: str) -> list[str]:
    """The number under every hash key, for matching a statement's payer."""
    return crypto.value_hashes(normalise_account(raw), scope=HASH_SCOPE)


@dataclass(frozen=True)
class NewAccount:
    currency: str
    country: str
    bank_name: str
    routing_code: str
    account_number: str
    holder_name: str


async def add(db: AsyncSession, user: User, new: NewAccount) -> BankAccount:
    """A verified business adds an account for a currency; it waits for
    finance. An earlier account for that currency is retired."""
    if not user.business.is_verified:
        raise Forbidden("Get your business verified before adding a bank account.")
    number = normalise_account(new.account_number)
    if not _ACCOUNT.fullmatch(number):
        raise BadRequest("Enter the account number or IBAN: 6 to 34 letters and digits.")
    routing = new.routing_code.strip().upper()
    if new.country == "IN" and not _IFSC.fullmatch(routing):
        raise BadRequest("Enter the branch's IFSC, e.g. HDFC0001234.")
    if new.country != "IN" and not _SWIFT.fullmatch(routing):
        raise BadRequest("Enter the bank's SWIFT/BIC code, e.g. EBILAEAD.")
    await db.execute(
        update(BankAccount)
        .where(BankAccount.business_id == user.business_id, BankAccount.currency == new.currency,
               BankAccount.status.in_(("pending", "verified")))
        .values(status="retired", retired_at=utcnow()).execution_options(synchronize_session=False)
    )
    account_ct, version = crypto.encrypt(number)
    holder_ct, _ = crypto.encrypt(" ".join(new.holder_name.split()))
    account = BankAccount(
        id=uuid.uuid4(), business_id=user.business_id, currency=new.currency, country=new.country,
        bank_name=new.bank_name.strip(), routing_code=routing, account_encrypted=account_ct,
        holder_encrypted=holder_ct, key_version=version, account_hash=crypto.value_hash(number, scope=HASH_SCOPE),
        account_last4=number[-4:], status="pending", created_by_user_id=user.id, created_at=utcnow(),
    )
    db.add(account)
    return account


async def own_accounts(db: AsyncSession, user: User) -> list[BankAccount]:
    return list(await db.scalars(
        select(BankAccount).where(BankAccount.business_id == user.business_id).order_by(BankAccount.created_at.desc())
    ))


async def _get(db: AsyncSession, account_id: uuid.UUID | None) -> BankAccount:
    account = await db.get(BankAccount, account_id) if account_id else None
    if account is None:
        raise NotFound("Bank account not found.")
    return account


async def verify(db: AsyncSession, admin_id: uuid.UUID, account_id: uuid.UUID | None, note: str) -> BankAccount:
    """Finance confirms the account (a penny drop, a bank letter). Payouts to
    it wait ``payout_cooling_off_hours`` from now."""
    account = await _get(db, account_id)
    if account.status != "pending":
        raise Conflict("Only an account waiting for verification can be verified.")
    hours = int(await settings_source.setting(db, seed.PAYOUT_COOLING_OFF_HOURS))
    now = utcnow()
    account.status, account.verified_by, account.verified_at = "verified", admin_id, now
    account.verification_note, account.cooling_off_until = note, now + timedelta(hours=hours)
    return account


async def reject(db: AsyncSession, account_id: uuid.UUID | None, reason: str) -> BankAccount:
    account = await _get(db, account_id)
    if account.status != "pending":
        raise Conflict("Only an account waiting for verification can be rejected.")
    account.status, account.rejected_reason = "rejected", reason
    return account


async def reveal(db: AsyncSession, account_id: uuid.UUID | None) -> tuple[BankAccount, str, str]:
    """The full number and holder, for the audited reveal only."""
    account = await _get(db, account_id)
    return (account, crypto.decrypt(account.account_encrypted, account.key_version),
            crypto.decrypt(account.holder_encrypted, account.key_version))


async def pending(db: AsyncSession) -> list[BankAccount]:
    return list(await db.scalars(
        select(BankAccount).where(BankAccount.status == "pending").order_by(BankAccount.created_at)
    ))


async def verified_hashes_of(db: AsyncSession, business_id: uuid.UUID) -> set[str]:
    """Every hash a verified account of the business can appear under: a
    statement line keeps the hash of the key in force when it was imported
    (its payer's number isn't stored), so a hash-key rotation must not stop
    it matching (CX-035)."""
    out: set[str] = set()
    for a in await db.scalars(
        select(BankAccount).where(BankAccount.business_id == business_id, BankAccount.status == "verified")
    ):
        out.update(account_hashes(crypto.decrypt(a.account_encrypted, a.key_version)))
    return out
