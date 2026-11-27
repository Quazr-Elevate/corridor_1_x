"""Default countries and KYB document types (India + UAE).

Migrations ``0021_kyb_profile`` / ``0023_countries`` insert frozen copies;
tests and fresh databases built with ``create_all`` use
:func:`default_country_rows` + :func:`default_rows`. Admins
edit the live list from the console afterwards."""
from __future__ import annotations

import uuid

#: The two countries a fresh database starts with. Not a catalogue of
#: countries an admin may pick from: every other country is typed in full in
#: /admin (there are no presets), so nothing but seeding reads this.
#: code: (name, flag, dial code, default currency)
COUNTRY_REFERENCE: dict[str, tuple[str, str, str, str]] = {
    "IN": ("India", "🇮🇳", "+91", "INR"),
    "AE": ("United Arab Emirates", "🇦🇪", "+971", "AED"),
}

#: Countries set up out of the box (their documents are below).
DEFAULT_COUNTRIES = ("IN", "AE")


def country_row(code: str, *, by: str = "system", active: bool = True) -> dict:
    name, flag, dial, currency = COUNTRY_REFERENCE[code]
    return {
        "code": code, "name": name, "flag": flag, "dial_code": dial, "default_currency": currency,
        "active": active, "created_by": by, "updated_by": by,
    }


def default_country_rows() -> list[dict]:
    return [country_row(c) for c in DEFAULT_COUNTRIES]


# (country, code, name, input_kind, pattern, placeholder, help, mandatory, sort)
DEFAULT_TYPES = (
    ("IN", "gstin", "GSTIN", "value", None, "22AAAAA0000A1Z5",
     "15-character GST Identification Number", True, 10),
    ("IN", "pan", "PAN", "value", None, "AAAAA0000A",
     "Permanent Account Number of the business", True, 20),
    ("IN", "udyam", "Udyam (MSME) registration", "value", r"UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}", "UDYAM-KA-01-0000000",
     None, False, 30),
    ("IN", "iec", "Import Export Code (IEC)", "value", r"[A-Z0-9]{10}", "AAAAA0000A",
     "Needed to export outside India", False, 40),
    ("IN", "fssai", "FSSAI licence", "value_and_file", r"[0-9]{14}", "10000000000000",
     "14-digit licence number and a copy of the licence", False, 50),
    ("AE", "trade_licence", "Trade licence", "file", None, None,
     "Copy of the valid trade licence", True, 10),
    ("AE", "trn", "Tax Registration Number (VAT)", "value", r"[0-9]{15}", "100000000000003",
     "15-digit UAE VAT TRN", False, 20),
)


#: Numbers several businesses may share: one PAN stands behind a company's
#: GSTIN in each state, and each GSTIN is its own business (A-052).
SHARED = {("IN", "pan")}

#: Per country: (quota document, group document) codes (A-052).
COUNTRY_LINKS = {"IN": ("gstin", "pan")}

#: Per country: (source code, start, end, target code) cross-checks (A-047).
#: None ship: numbers are checked by the reviewer and the upstream provider,
#: not by country-specific rules in Corridor (0041). Admins may add their own.
DEFAULT_RULES: tuple[tuple[str, str, int, int, str], ...] = ()


def default_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "country": c, "code": code, "name": name, "input_kind": kind,
            "value_pattern": pattern, "value_placeholder": placeholder, "help_text": help_,
            "is_mandatory": mandatory, "is_unique": (c, code) not in SHARED, "sort_order": sort, "active": True,
        }
        for c, code, name, kind, pattern, placeholder, help_, mandatory, sort in DEFAULT_TYPES
    ]


def default_rule_rows(type_rows: list[dict]) -> list[dict]:
    ids = {(r["country"], r["code"]): r["id"] for r in type_rows}
    return [
        {
            "id": uuid.uuid4(), "country": c, "kind": "slice_equals", "source_type_id": ids[(c, src)],
            "source_start": start, "source_end": end, "target_type_id": ids[(c, dst)], "active": True,
        }
        for c, src, start, end, dst in DEFAULT_RULES
    ]


def default_country_links(type_rows: list[dict]) -> dict[str, dict]:
    """``{country: {"quota_document_type_id": …, "group_document_type_id": …}}``."""
    ids = {(r["country"], r["code"]): r["id"] for r in type_rows}
    return {
        c: {"quota_document_type_id": ids[(c, quota)], "group_document_type_id": ids[(c, group)]}
        for c, (quota, group) in COUNTRY_LINKS.items()
    }
