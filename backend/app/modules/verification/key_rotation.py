"""Move stored KYB values to the newest keys (CX-035, A-080).

Run after adding a key, through ``scripts/rotate_keys.py``:

* a KYB number encrypted under an older ``KYB_ENC_KEYS`` version is
  re-encrypted under the newest; once no value uses a version, that key can
  be removed from the list;
* bank accounts (CX-020) are re-encrypted and their match hash moved the same way;
* a keyed hash written under a key now in ``KYB_HASH_KEY_PREVIOUS`` is
  recomputed under ``KYB_HASH_KEY``, and a free-quota row carrying the old
  hash of a number still on file moves with it.

Idempotent and resumable: each batch commits on its own, and a value already
on the newest keys is left alone. Nothing here logs or returns a number."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models.admin_user import AdminUser
from app.models.banking import BankAccount
from app.models.business_document import BusinessDocument
from app.models.credits import CreditFreeQuota
from app.models.user import User

BATCH = 500


@dataclass
class RotationReport:
    reencrypted: int = 0
    rehashed: int = 0
    quotas_moved: int = 0
    #: A quota row whose number already has a row under the new key: left as it is.
    quota_clashes: int = 0
    #: Encrypted values per key version after the run (or, dry, as they would be).
    by_version: Counter = field(default_factory=Counter)
    #: Authenticator secrets on file. No code writes them yet; when it does,
    #: they join this rotation.
    totp_secrets: int = 0


def _scope(doc: BusinessDocument) -> str:
    # The scope verification.service._set_value hashes under.
    return str(doc.document_type_id) if doc.document_type_id else "other"


async def rotate(db: AsyncSession, *, apply: bool) -> RotationReport:
    """Re-encrypt and rehash every KYB value not on the newest keys. With
    ``apply=False`` nothing is written; the report says what would change."""
    report = RotationReport()
    current = crypto.current_version()
    moved: dict[str, str] = {}
    last_id = None
    while True:
        stmt = select(BusinessDocument).where(BusinessDocument.value_encrypted.is_not(None)).order_by(BusinessDocument.id)
        if last_id is not None:
            stmt = stmt.where(BusinessDocument.id > last_id)
        docs = list(await db.scalars(stmt.limit(BATCH)))
        if not docs:
            break
        for doc in docs:
            value = crypto.decrypt(doc.value_encrypted, doc.value_key_version)
            if doc.value_key_version != current:
                report.reencrypted += 1
                if apply:
                    doc.value_encrypted, doc.value_key_version = crypto.encrypt(value)
            new_hash = crypto.value_hash(value, scope=_scope(doc))
            if doc.value_hash != new_hash:
                report.rehashed += 1
                moved[doc.value_hash] = new_hash
                if apply:
                    doc.value_hash = new_hash
            report.by_version[current if apply else doc.value_key_version] += 1
        last_id = docs[-1].id
        if apply:
            await db.commit()

    # Bank accounts (CX-020): the number and holder share one key version; the
    # hash is what statement lines are matched by, so it moves too.
    for account in list(await db.scalars(select(BankAccount))):
        number = crypto.decrypt(account.account_encrypted, account.key_version)
        if account.key_version != current:
            report.reencrypted += 1
            if apply:
                holder = crypto.decrypt(account.holder_encrypted, account.key_version)
                account.account_encrypted, account.key_version = crypto.encrypt(number)
                account.holder_encrypted, _ = crypto.encrypt(holder)
        new_hash = crypto.value_hash(number, scope="bank_account")
        if account.account_hash != new_hash:
            report.rehashed += 1
            if apply:
                account.account_hash = new_hash
        report.by_version[current if apply else account.key_version] += 1
    if apply:
        await db.commit()

    for old, new in moved.items():
        for quota in list(await db.scalars(select(CreditFreeQuota).where(CreditFreeQuota.registration_hash == old))):
            clash = await db.scalar(select(CreditFreeQuota.id).where(
                CreditFreeQuota.action == quota.action, CreditFreeQuota.registration_hash == new
            ))
            if clash is not None:
                report.quota_clashes += 1
                continue
            report.quotas_moved += 1
            if apply:
                quota.registration_hash = new
    if apply:
        await db.commit()

    report.totp_secrets = sum([
        await db.scalar(select(func.count()).select_from(User).where(User.totp_secret_encrypted.is_not(None))) or 0,
        await db.scalar(select(func.count()).select_from(AdminUser).where(AdminUser.totp_secret_encrypted.is_not(None))) or 0,
    ])
    return report
