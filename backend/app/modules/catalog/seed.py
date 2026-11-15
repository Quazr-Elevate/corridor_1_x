"""Default listing templates: specification parameters and certificate types.

Migration ``0026_listing_review`` inserts a frozen copy; tests and fresh
databases built with ``create_all`` use :func:`default_spec_rows` and
:func:`default_certificate_rows`. Admins edit the live lists afterwards.

Rice follows the build plan's worked example (3.2) and is required. The
Spices and Pulses rows are common trade parameters offered as optional
starting points; no limits are set here — the seller states the value.
"""
from __future__ import annotations

import uuid

from app.models.listing import ALL_CATEGORIES

# (category, code, name, unit, default operator, required, sort)
DEFAULT_SPECS = (
    ("Rice", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Rice", "broken_grains", "Broken grains", "%", "MAX", True, 20),
    ("Rice", "foreign_matter", "Foreign matter", "%", "MAX", True, 30),
    ("Rice", "grain_length", "Grain length", "mm", "MIN", True, 40),
    ("Spices", "moisture", "Moisture", "%", "MAX", False, 10),
    ("Spices", "volatile_oil", "Volatile oil", "%", "MIN", False, 20),
    ("Spices", "total_ash", "Total ash", "%", "MAX", False, 30),
    ("Spices", "foreign_matter", "Foreign matter", "%", "MAX", False, 40),
    ("Pulses", "moisture", "Moisture", "%", "MAX", False, 10),
    ("Pulses", "foreign_matter", "Foreign matter", "%", "MAX", False, 20),
    ("Pulses", "damaged_grains", "Damaged grains", "%", "MAX", False, 30),
    ("Pulses", "weevilled_grains", "Weevilled grains", "%", "MAX", False, 40),
)

# (category, code, name, help, required, sort)
DEFAULT_CERTIFICATES = (
    (ALL_CATEGORIES, "coa", "Certificate of analysis (COA)", "Lab-issued, with the batch or lot number.", False, 10),
    (ALL_CATEGORIES, "quality_test_report", "Quality test report", "Third-party report, within its validity.", False, 20),
    (ALL_CATEGORIES, "product_certificate", "Product certificate", "For example FSSAI, Organic or Fair-Trade.", False, 30),
)


def default_spec_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "category": category, "code": code, "name": name, "value_type": "number",
            "unit": unit, "default_operator": operator, "test_method": None, "is_required": required,
            "sort_order": sort, "active": True,
        }
        for category, code, name, unit, operator, required, sort in DEFAULT_SPECS
    ]


def default_certificate_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "category": category, "code": code, "name": name, "help_text": help_text,
            "is_required": required, "sort_order": sort, "active": True,
        }
        for category, code, name, help_text, required, sort in DEFAULT_CERTIFICATES
    ]
