"""Starting values of ``trade_settings``. The client decides most of them
(decisions A-037, A-040); those rows are placeholders until an admin sets
them."""
from __future__ import annotations

from decimal import Decimal

RFQ_OPEN_DAYS = "rfq_open_days"
QUOTE_VALID_DAYS = "quote_valid_days"
MIN_MARGIN_PCT = "min_margin_pct"
FX_BUFFER_PCT = "fx_buffer_pct"
FREIGHT_MAX_AGE_DAYS = "freight_max_age_days"

# key, value, placeholder
_SETTINGS = (
    (RFQ_OPEN_DAYS, "14", True),
    (QUOTE_VALID_DAYS, "7", True),
    (MIN_MARGIN_PCT, "5", True),
    (FX_BUFFER_PCT, "2", True),
    (FREIGHT_MAX_AGE_DAYS, "7", False),  # plan 6.3: a freight quote older than this is refused
)


def default_setting_rows() -> list[dict]:
    return [{"key": k, "value": Decimal(v), "is_placeholder": p} for k, v, p in _SETTINGS]
