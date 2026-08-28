"""PII display helpers.

Rule of thumb: never emit raw sensitive identifiers in API responses that
render in a UI. Store them plaintext (DB is encrypted at rest by the
infrastructure), but always mask on the way out.

Aadhaar Act 2016 mandates that the full 12-digit number never be displayed;
only the last 4 characters are safe to show. We apply the same discipline
to bank account numbers.
"""
from __future__ import annotations


def mask_aadhaar(value: str | None) -> str | None:
    """Return e.g. 'XXXX XXXX 1234' for a 12-digit Aadhaar. Unknown formats
    (empty, too short) are returned as fully masked with the last 4 kept."""
    if not value:
        return value
    stripped = "".join(ch for ch in value if ch.isalnum())
    if len(stripped) <= 4:
        return "X" * len(stripped)
    last4 = stripped[-4:]
    return f"XXXX XXXX {last4}" if len(stripped) == 12 else f"XXXX{last4}"


def mask_bank_account(value: str | None) -> str | None:
    """Show only the last 4 digits of an account number: 'XXXXXX1234'."""
    if not value:
        return value
    stripped = value.strip()
    if len(stripped) <= 4:
        return "X" * len(stripped)
    return "X" * (len(stripped) - 4) + stripped[-4:]
