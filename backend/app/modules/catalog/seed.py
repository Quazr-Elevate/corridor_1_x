"""Default listing templates: specification parameters and certificate types.

Migration ``0026_listing_review`` inserts a frozen copy; tests and fresh
databases built with ``create_all`` use :func:`default_spec_rows` and
:func:`default_certificate_rows`. Admins edit the live lists afterwards.

Rice follows the build plan's worked example (3.2). The other categories
are the templates approved in the M0–M3 walkthrough review (A-049), with
the documents each category requires. No limits are set here: the seller
states the value, the buyer sets the limit.
"""
from __future__ import annotations

import uuid

from app.models.listing import ALL_CATEGORIES

# (category, code, name, unit, default operator, required, sort[, value type])
# Rice follows the build plan; the other categories are the templates
# approved in the M0–M3 walkthrough review (A-049).
DEFAULT_SPECS = (
    ("Rice", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Rice", "broken_grains", "Broken grains", "%", "MAX", True, 20),
    ("Rice", "foreign_matter", "Foreign matter", "%", "MAX", True, 30),
    ("Rice", "grain_length", "Grain length", "mm", "MIN", True, 40),
    ("Spices", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Spices", "volatile_oil", "Volatile oil", "%", "MIN", True, 20),
    ("Spices", "total_ash", "Total ash", "%", "MAX", False, 30),
    ("Spices", "foreign_matter", "Foreign matter", "%", "MAX", False, 40),
    ("Pulses", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Pulses", "foreign_matter", "Foreign matter", "%", "MAX", True, 20),
    ("Pulses", "damaged_grains", "Damaged grains", "%", "MAX", False, 30),
    ("Pulses", "weevilled_grains", "Weevilled grains", "%", "MAX", False, 40),
    ("Sugar", "icumsa", "ICUMSA colour", "IU", "MAX", True, 10),
    ("Sugar", "polarisation", "Polarisation", "°Z", "MIN", True, 20),
    ("Sugar", "moisture", "Moisture", "%", "MAX", True, 30),
    ("Sugar", "ash", "Ash", "%", "MAX", False, 40),
    ("Sugar", "solubility", "Solubility", "%", "MIN", False, 50),
    ("Sugar", "granulation", "Granulation", None, "EQ", False, 60, "text"),
    ("Wheat", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Wheat", "protein", "Protein", "%", "MIN", True, 20),
    ("Wheat", "foreign_matter", "Foreign matter", "%", "MAX", True, 30),
    ("Wheat", "test_weight", "Test weight", "kg/hl", "MIN", False, 40),
    ("Wheat", "falling_number", "Falling number", "s", "MIN", False, 50),
    ("Wheat", "damaged_kernels", "Damaged kernels", "%", "MAX", False, 60),
    ("Oilseeds", "oil_content", "Oil content", "%", "MIN", True, 10),
    ("Oilseeds", "moisture", "Moisture", "%", "MAX", True, 20),
    ("Oilseeds", "free_fatty_acid", "Free fatty acid", "%", "MAX", True, 30),
    ("Oilseeds", "aflatoxin", "Aflatoxin", "ppb", "MAX", True, 40),
    ("Oilseeds", "foreign_matter", "Foreign matter", "%", "MAX", False, 50),
    ("Oilseeds", "admixture", "Admixture", "%", "MAX", False, 60),
    ("Cotton", "staple_length", "Staple length", "mm", "MIN", True, 10),
    ("Cotton", "micronaire", "Micronaire", None, "EQ", True, 20, "text"),
    ("Cotton", "strength", "Strength", "g/tex", "MIN", True, 30),
    ("Cotton", "trash", "Trash", "%", "MAX", False, 40),
    ("Cotton", "moisture", "Moisture", "%", "MAX", False, 50),
    ("Millets", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Millets", "foreign_matter", "Foreign matter", "%", "MAX", True, 20),
    ("Millets", "damaged_grains", "Damaged grains", "%", "MAX", False, 30),
    ("Millets", "other_grains", "Other grains", "%", "MAX", False, 40),
    ("Millets", "immature_grains", "Immature or shrivelled grains", "%", "MAX", False, 50),
    ("Tea", "grade", "Grade", None, "EQ", True, 10, "text"),
    ("Tea", "moisture", "Moisture", "%", "MAX", True, 20),
    ("Tea", "total_ash", "Total ash", "%", "MAX", False, 30),
    ("Tea", "water_extract", "Water extract", "%", "MIN", False, 40),
    ("Tea", "crude_fibre", "Crude fibre", "%", "MAX", False, 50),
    ("Coffee", "type", "Type", None, "EQ", True, 10, "text"),
    ("Coffee", "moisture", "Moisture", "%", "MAX", True, 20),
    ("Coffee", "screen_size", "Screen size", "screen", "MIN", True, 30),
    ("Coffee", "defects", "Defects per 300 g", "count", "MAX", True, 40),
    ("Coffee", "cup_score", "Cup score", "points", "MIN", False, 50),
    ("Other", "moisture", "Moisture", "%", "MAX", False, 10),
    ("Other", "foreign_matter", "Foreign matter", "%", "MAX", False, 20),
)

# (category, code, name, help, required, sort)
DEFAULT_CERTIFICATES = (
    (ALL_CATEGORIES, "coa", "Certificate of analysis (COA)", "Lab-issued, with the batch or lot number.", False, 10),
    (ALL_CATEGORIES, "quality_test_report", "Quality test report", "Third-party report, within its validity.", False, 20),
    (ALL_CATEGORIES, "product_certificate", "Product certificate", "For example FSSAI, Organic or Fair-Trade.", False, 30),
)


#: (category, certificate type code): the documents a listing in that
#: category must carry (A-049).
DEFAULT_REQUIREMENTS = (
    ("Rice", "coa"),
    ("Spices", "coa"), ("Spices", "quality_test_report"),
    ("Pulses", "coa"),
    ("Sugar", "coa"),
    ("Wheat", "coa"),
    ("Oilseeds", "coa"), ("Oilseeds", "quality_test_report"),
    ("Cotton", "quality_test_report"),
    ("Millets", "coa"),
    ("Tea", "product_certificate"),
    ("Coffee", "quality_test_report"),
)


def default_spec_rows() -> list[dict]:
    rows = []
    for spec in DEFAULT_SPECS:
        category, code, name, unit, operator, required, sort = spec[:7]
        rows.append({
            "id": uuid.uuid4(), "category": category, "code": code, "name": name,
            "value_type": spec[7] if len(spec) > 7 else "number", "unit": unit, "default_operator": operator,
            "test_method": None, "is_required": required, "sort_order": sort, "active": True,
        })
    return rows


def default_requirement_rows(certificate_rows: list[dict]) -> list[dict]:
    ids = {r["code"]: r["id"] for r in certificate_rows if r["category"] == ALL_CATEGORIES}
    return [{"category": category, "certificate_type_id": ids[code]} for category, code in DEFAULT_REQUIREMENTS]


def default_certificate_rows() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(), "category": category, "code": code, "name": name, "help_text": help_text,
            "is_required": required, "sort_order": sort, "active": True,
        }
        for category, code, name, help_text, required, sort in DEFAULT_CERTIFICATES
    ]
