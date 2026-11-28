"""/me/bank-accounts — a business's own bank accounts (CX-020)."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.crypto import mask
from app.models.banking import BankAccount
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.banking import accounts
from app.modules.banking.schemas import BankAccountIn, BankAccountOut
from app.shared.schemas import ItemList, item_list

router = APIRouter(prefix="/me/bank-accounts", tags=["me"])


def account_out(a: BankAccount) -> BankAccountOut:
    return BankAccountOut(
        id=str(a.id), currency=a.currency, country=a.country, bank_name=a.bank_name, routing_code=a.routing_code,
        account_masked=mask(a.account_last4), status=a.status, rejected_reason=a.rejected_reason,
        created_at=a.created_at,
    )


@router.get("", response_model=ItemList[BankAccountOut], response_model_by_alias=True)
async def list_accounts(user: CurrentUser, db: DbSession) -> ItemList[BankAccountOut]:
    """Your business's accounts, newest first, numbers masked."""
    return item_list([account_out(a) for a in await accounts.own_accounts(db, user)])


@router.post("", response_model=BankAccountOut, response_model_by_alias=True, status_code=201)
async def add_account(payload: BankAccountIn, user: CurrentUser, db: DbSession) -> BankAccountOut:
    """Add the account for a currency. Corridor One X verifies it before any
    payment uses it; an earlier account for that currency is retired."""
    a = await accounts.add(db, user, accounts.NewAccount(**payload.model_dump()))
    await db.commit()
    return account_out(a)
