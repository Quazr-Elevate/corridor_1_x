"""/admin/companies/{code}/unmask — who is behind a company code.

Staff work from codes (``IN-482913``). Turning one back into a name needs the
``identity.unmask`` permission and a stated reason, and is written to
``admin_actions`` as ``identity.unmasked``."""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.admin.deps import CanUnmaskIdentity
from app.modules.admin.schemas import AccessReasonIn, UnmaskedCompany
from app.modules.auth.deps import DbSession
from app.modules.masking import service as masking

router = APIRouter()


@router.post("/companies/{company_code}/unmask", response_model=UnmaskedCompany, response_model_by_alias=True)
async def unmask_company(
    company_code: str, payload: AccessReasonIn, admin: CanUnmaskIdentity, db: DbSession
) -> UnmaskedCompany:
    """POST, not GET: the reason travels in the body, out of URLs and access logs."""
    business = await masking.business_by_code(db, company_code)
    identity = await masking.unmask_for_staff(db, admin, business.id, purpose="code_lookup", reason=payload.reason)
    await db.commit()
    return UnmaskedCompany(
        company_code=business.company_code,
        business_id=str(business.id),
        legal_name=identity.legal_name,
        address_line=identity.address_line,
        state=business.state,
        country=business.country,
        website_url=identity.website_url,
    )
