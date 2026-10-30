"""Default KYB document types (India + UAE).

Migration ``0021_kyb_profile`` inserts a frozen copy of this list; tests and
fresh databases built with ``create_all`` use :func:`default_rows`. Admins
edit the live list from the console afterwards."""
from __future__ import annotations

import uuid

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
