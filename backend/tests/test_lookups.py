"""PIN code and IFSC lookups: sign-in required, rate limited, cached."""
from __future__ import annotations

import pytest
from conftest import signup_and_login

from app.integrations.lookups import IfscResult, PincodeError, PincodeInvalid, PincodeResult
from app.main import app
from app.modules.lookups.router import LOOKUP_PER_PRINCIPAL, get_ifsc_lookup, get_pincode_lookup


class _Pincodes:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def lookup(self, pincode: str) -> PincodeResult:
        self.calls.append(pincode)
        if not pincode.isdigit() or len(pincode) != 6:
            raise PincodeInvalid("Enter a valid 6-digit pincode.")
        if pincode == "999999":
            raise PincodeError("No location found for this pincode")
        return PincodeResult(pincode=pincode, city="Mysuru", district="Mysuru", state="Karnataka")


class _Ifscs:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def lookup(self, code: str) -> IfscResult:
        self.calls.append(code)
        return IfscResult(ifsc=code, bank="State Bank of India", branch="Mysuru Main", city="Mysuru", state="Karnataka")


@pytest.fixture
def lookups():
    pincodes, ifscs = _Pincodes(), _Ifscs()
    app.dependency_overrides[get_pincode_lookup] = lambda: pincodes
    app.dependency_overrides[get_ifsc_lookup] = lambda: ifscs
    yield pincodes, ifscs
    app.dependency_overrides.pop(get_pincode_lookup, None)
    app.dependency_overrides.pop(get_ifsc_lookup, None)


async def test_lookups_require_a_session(client, lookups):
    pincodes, ifscs = lookups
    for path in ("/pincode/570001", "/ifsc/SBIN0000001"):
        r = await client.get(path)
        assert r.status_code == 401, path
    assert pincodes.calls == [] and ifscs.calls == []


async def test_trader_lookup_is_cached(client, lookups):
    pincodes, ifscs = lookups
    await signup_and_login(client, "lookup1@kaverifoods.in")
    for _ in range(3):
        r = await client.get("/pincode/570001")
        assert r.status_code == 200, r.text
        assert r.json() == {"pincode": "570001", "city": "Mysuru", "district": "Mysuru", "state": "Karnataka"}
    assert pincodes.calls == ["570001"]

    # The code is normalised before it is used as the cache key.
    for code in ("SBIN0000001", "sbin0000001"):
        r = await client.get(f"/ifsc/{code}")
        assert r.status_code == 200 and r.json()["ifsc"] == "SBIN0000001"
    assert ifscs.calls == ["SBIN0000001"]


async def test_a_failed_lookup_is_not_cached(client, lookups):
    pincodes, _ = lookups
    await signup_and_login(client, "lookup2@kaverifoods.in")
    for _ in range(2):
        r = await client.get("/pincode/999999")
        assert r.status_code == 404
    assert pincodes.calls == ["999999", "999999"]


async def test_admin_can_look_up(admin_client, lookups):
    r = await admin_client.get("/pincode/570001")
    assert r.status_code == 200, r.text


async def test_lookups_are_rate_limited_per_principal(client, make_client, lookups):
    await signup_and_login(client, "lookup3@kaverifoods.in")
    for _ in range(LOOKUP_PER_PRINCIPAL.limit):
        assert (await client.get("/pincode/570001")).status_code == 200
    r = await client.get("/ifsc/SBIN0000001")
    assert r.status_code == 429 and "Retry-After" in r.headers

    # The limit is per signed-in principal, not shared.
    other = make_client()
    await signup_and_login(other, "lookup4@kaverifoods.in")
    assert (await other.get("/pincode/570001")).status_code == 200


async def test_a_malformed_pincode_is_a_bad_request_not_a_missing_one(client, lookups):
    await signup_and_login(client, "lookup3@kaverifoods.in")
    r = await client.get("/pincode/12AB")
    assert r.status_code == 400 and r.json()["code"] == "request.invalid"
    assert (await client.get("/pincode/999999")).status_code == 404
