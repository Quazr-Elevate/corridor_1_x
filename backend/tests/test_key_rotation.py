"""Key rotation (M4 · S8, CX-035, A-080): every server secret can change
without signing anyone out or breaking a check. An old SESSION_SECRET still
accepts codes it sent; an old KYB hash key still matches until
scripts/rotate_keys.py moves the stored hashes, and keeps matching free-quota
rows that can't be moved; old encryption keys can be removed once the script
reports them unused."""
from __future__ import annotations

import base64
import uuid

import pytest
from conftest import code_from_email, fill_mandatory, set_status, signup_and_login
from sqlalchemy import select

from app.core import crypto
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Business, BusinessStatus, CreditFreeQuota, User
from app.models.business_document import BusinessDocument
from app.modules.credits import service as credits
from app.modules.verification.key_rotation import rotate

_K = {c: base64.b64encode(c.encode() * 32).decode() for c in "kKLhH"}


@pytest.fixture
def keys(monkeypatch):
    """Swap the server's keys mid-test, as a deploy with new settings would."""
    def use(**values):
        for name, value in values.items():
            monkeypatch.setattr(settings, name, value)
        crypto._keys.cache_clear()

    yield use
    crypto._keys.cache_clear()


async def test_a_code_sent_before_a_session_secret_rotation_still_works(client, keys):
    email = "rot1@kaverifoods.in"
    assert (await client.post("/auth/signup/code", json={"email": email})).status_code == 200
    code = code_from_email(email)
    old = settings.session_secret
    keys(session_secret="a-brand-new-session-secret-0123456789")
    # Without the old secret listed, the code no longer checks.
    assert (await client.post("/auth/signup/verify", json={"email": email, "code": code})).status_code == 400
    keys(session_secret_previous=old)
    r = await client.post("/auth/signup/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text


def test_previous_hash_keys_are_checked_at_startup(keys):
    keys(kyb_hash_key_previous=_K["h"])
    with pytest.raises(crypto.CryptoConfigError):
        crypto.load_keys(settings)  # the same as the current key
    keys(kyb_hash_key_previous="not-base64!")
    with pytest.raises(crypto.CryptoConfigError):
        crypto.load_keys(settings)
    keys(kyb_hash_key_previous=_K["H"])
    assert crypto.load_keys(settings).previous_hash_keys == (b"H" * 32,)


async def _docs(user_id: str) -> list[BusinessDocument]:
    async with SessionLocal() as db:
        business_id = (await db.get(User, uuid.UUID(user_id))).business_id
        return list(await db.scalars(
            select(BusinessDocument).where(BusinessDocument.business_id == business_id, BusinessDocument.value_hash.is_not(None))
        ))


async def test_a_hash_key_rotation_keeps_duplicates_refused_and_the_script_moves_everything(client, make_client, keys):
    me = await signup_and_login(client, "rot2@kaverifoods.in")
    await fill_mandatory(client, n=7)
    await set_status(me["userId"], BusinessStatus.verified)
    async with SessionLocal() as db:
        business = await db.get(Business, (await db.get(User, uuid.UUID(me["userId"]))).business_id)
        quota = await credits._quota(db, business, "RFQ_POST")
        quota.used = 3
        await db.commit()
        old_quota_hash = quota.registration_hash
    before = {d.id: (d.value_hash, d.value_key_version) for d in await _docs(me["userId"])}
    assert before and all(v == 2 for _, v in before.values())

    # A new hash key and a new encryption key are deployed; the old ones are kept.
    keys(
        kyb_enc_keys=f"{settings.kyb_enc_keys},3:{_K['L']}",
        kyb_hash_key=_K["H"],
        kyb_hash_key_previous=_K["h"],
    )
    # Before the script runs, the same GSTIN on another company is still refused.
    other = make_client()
    await signup_and_login(other, "rot3@othermill.in")
    await fill_mandatory(other, n=8)
    types = {t["code"]: t["id"] for t in (await other.get("/kyb/document-types")).json()["items"]}
    r = await other.post("/me/verification-docs", data={"documentTypeId": types["gstin"], "value": "07AAAAA0007A1Z5"})
    assert r.status_code == 409, r.text

    async with SessionLocal() as db:
        dry = await rotate(db, apply=False)
    assert dry.reencrypted >= len(before) and dry.rehashed >= len(before) and dry.quotas_moved == 1
    assert {d.id: (d.value_hash, d.value_key_version) for d in await _docs(me["userId"])} == before  # nothing written

    async with SessionLocal() as db:
        done = await rotate(db, apply=True)
    assert done.reencrypted == dry.reencrypted and done.quotas_moved == 1 and done.by_version == {3: done.by_version[3]}
    after = await _docs(me["userId"])
    assert all(d.value_key_version == 3 and d.value_hash != before[d.id][0] for d in after)
    async with SessionLocal() as db:
        quota = await db.scalar(select(CreditFreeQuota).where(CreditFreeQuota.business_id == business.id))
    assert quota.registration_hash != old_quota_hash and quota.used == 3  # the count came with it

    # A second run finds nothing to do, and versions 1 and 2 can go.
    async with SessionLocal() as db:
        again = await rotate(db, apply=True)
    assert (again.reencrypted, again.rehashed, again.quotas_moved) == (0, 0, 0)
    keys(kyb_enc_keys=f"3:{_K['L']}")
    r = await client.get("/me/verification-docs")
    assert r.status_code == 200


async def test_an_old_quota_row_is_found_and_moved_when_the_number_comes_back(client, keys):
    me = await signup_and_login(client, "rot4@kaverifoods.in")
    await fill_mandatory(client, n=9)
    await set_status(me["userId"], BusinessStatus.verified)
    async with SessionLocal() as db:
        business = await db.get(Business, (await db.get(User, uuid.UUID(me["userId"]))).business_id)
        old = (await credits.registration_hashes(db, business))[0]
        # A deleted company with the same number left this row under the old key.
        db.add(CreditFreeQuota(action="RFQ_POST", registration_hash=old, business_id=None, allowance=10, used=10))
        await db.commit()
    keys(kyb_hash_key=_K["H"], kyb_hash_key_previous=_K["h"])
    async with SessionLocal() as db:
        business = await db.get(Business, business.id)
        quota = await credits._quota(db, business, "RFQ_POST")
        await db.commit()
        assert quota.used == 10  # no fresh set of free requests
        assert quota.registration_hash == (await credits.registration_hashes(db, business))[0] != old
