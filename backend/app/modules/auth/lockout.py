"""Account lockout after repeated wrong passwords (users and admins).

* 5 wrong passwords in a row → locked for 15 minutes;
* each further lockout doubles it (15 → 30 minutes);
* the 3rd lockout locks the account until support unlocks it
  (``lockout_count >= SUPPORT_AFTER`` with ``locked_until`` null).

A successful sign-in resets both counters. While locked, the password is
not checked at all. Works on any model with ``failed_login_count``,
``lockout_count`` and ``locked_until`` (``User``, ``AdminUser``).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.errors import Locked
from app.core.time import ensure_aware

MAX_FAILED = 5
BASE_LOCK = timedelta(minutes=15)
SUPPORT_AFTER = 3


def needs_support(acct: Any) -> bool:
    return acct.lockout_count >= SUPPORT_AFTER


def lock_state(acct: Any, now: datetime) -> str:
    """``none`` | ``temporary`` | ``support``."""
    if needs_support(acct):
        return "support"
    if acct.locked_until is not None and ensure_aware(acct.locked_until) > now:
        return "temporary"
    return "none"


def support_message() -> str:
    return (
        "This account is locked after repeated failed sign-in attempts. "
        f"Please contact support at {settings.support_email} to unlock it."
    )


def ensure_not_locked(acct: Any, now: datetime) -> None:
    state = lock_state(acct, now)
    if state == "support":
        raise Locked(support_message())
    if state == "temporary":
        seconds = (ensure_aware(acct.locked_until) - now).total_seconds()
        minutes = max(1, math.ceil(seconds / 60))
        raise Locked(
            f"Too many failed sign-in attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(max(1, int(seconds)))},
        )


def record_failure(acct: Any, now: datetime) -> str | None:
    """Count a wrong password. Returns ``locked`` / ``locked_support`` when
    this attempt triggered a lockout, else None."""
    acct.failed_login_count += 1
    if acct.failed_login_count < MAX_FAILED:
        return None
    acct.failed_login_count = 0
    acct.lockout_count += 1
    if needs_support(acct):
        acct.locked_until = None
        return "locked_support"
    acct.locked_until = now + BASE_LOCK * (2 ** (acct.lockout_count - 1))
    return "locked"


def record_success(acct: Any) -> None:
    acct.failed_login_count = 0
    acct.lockout_count = 0
    acct.locked_until = None


unlock = record_success
