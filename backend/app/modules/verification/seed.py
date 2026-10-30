"""Default countries and KYB document types (India + UAE).

Migrations ``0021_kyb_profile`` / ``0023_countries`` insert frozen copies;
tests and fresh databases built with ``create_all`` use
:func:`default_country_rows` + :func:`default_rows`. Admins
edit the live list from the console afterwards."""
from __future__ import annotations

import uuid

#: Reference data for countries an admin may add (pre-fills the form).
#: code: (name, flag, dial code, default currency, region label, postal label, postal pattern)
COUNTRY_REFERENCE: dict[str, tuple[str, str, str, str, str, str, str | None]] = {
    "IN": ("India", "🇮🇳", "+91", "INR", "State", "PIN code", r"[1-9][0-9]{5}"),
    "AE": ("United Arab Emirates", "🇦🇪", "+971", "AED", "Emirate", "PO Box", None),
    "SA": ("Saudi Arabia", "🇸🇦", "+966", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "OM": ("Oman", "🇴🇲", "+968", "USD", "Governorate", "Postal code", r"[0-9]{3}"),
    "QA": ("Qatar", "🇶🇦", "+974", "USD", "Municipality", "PO Box", None),
    "KW": ("Kuwait", "🇰🇼", "+965", "USD", "Governorate", "Postal code", r"[0-9]{5}"),
    "BH": ("Bahrain", "🇧🇭", "+973", "USD", "Governorate", "Postal code", r"[0-9]{3,4}"),
    "US": ("United States", "🇺🇸", "+1", "USD", "State", "ZIP code", r"[0-9]{5}(-[0-9]{4})?"),
    "GB": ("United Kingdom", "🇬🇧", "+44", "USD", "County", "Postcode", None),
    "DE": ("Germany", "🇩🇪", "+49", "USD", "State", "Postal code", r"[0-9]{5}"),
    "NL": ("Netherlands", "🇳🇱", "+31", "USD", "Province", "Postal code", r"[0-9]{4}\s?[A-Z]{2}"),
    "SG": ("Singapore", "🇸🇬", "+65", "USD", "Region", "Postal code", r"[0-9]{6}"),
    "MY": ("Malaysia", "🇲🇾", "+60", "USD", "State", "Postcode", r"[0-9]{5}"),
    "ID": ("Indonesia", "🇮🇩", "+62", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "TH": ("Thailand", "🇹🇭", "+66", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "VN": ("Vietnam", "🇻🇳", "+84", "USD", "Province", "Postal code", r"[0-9]{6}"),
    "JP": ("Japan", "🇯🇵", "+81", "USD", "Prefecture", "Postal code", r"[0-9]{3}-?[0-9]{4}"),
    "CN": ("China", "🇨🇳", "+86", "USD", "Province", "Postal code", r"[0-9]{6}"),
    "KR": ("South Korea", "🇰🇷", "+82", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "AU": ("Australia", "🇦🇺", "+61", "USD", "State", "Postcode", r"[0-9]{4}"),
}

#: Countries set up out of the box (their documents are below).
DEFAULT_COUNTRIES = ("IN", "AE")


def country_row(code: str, *, by: str = "system", active: bool = True) -> dict:
    name, flag, dial, currency, region, postal, pattern = COUNTRY_REFERENCE[code]
    return {
        "code": code, "name": name, "flag": flag, "dial_code": dial, "default_currency": currency,
        "region_label": region, "postal_label": postal, "postal_pattern": pattern, "active": active,
        "created_by": by, "updated_by": by,
    }


def default_country_rows() -> list[dict]:
    return [country_row(c) for c in DEFAULT_COUNTRIES]


# (country, code, name, input_kind, pattern, placeholder, help, mandatory, sort)
DEFAULT_TYPES = (
    ("IN", "gstin", "GSTIN", "value", r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", "22AAAAA0000A1Z5",
     "15-character GST Identification Number", True, 10),
    ("IN", "pan", "PAN", "value", r"[A-Z]{5}[0-9]{4}[A-Z]", "AAAAA0000A",
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


def default_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "country": c, "code": code, "name": name, "input_kind": kind,
            "value_pattern": pattern, "value_placeholder": placeholder, "help_text": help_,
            "is_mandatory": mandatory, "is_unique": True, "sort_order": sort, "active": True,
        }
        for c, code, name, kind, pattern, placeholder, help_, mandatory, sort in DEFAULT_TYPES
    ]
