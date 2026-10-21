"""Email-address validation layered defense.

Three cheap checks before the signup table is touched:

  1. Shape — needs ``@`` and a TLD.
  2. Free-mail blocklist (gmail / outlook / yahoo / ...). B2B apps
     almost never accept personal addresses; this block saves support
     from untangling "I used my gmail" tickets later.
  3. Disposable blocklist — the ~9k-domain list from
     ``disposable-email-domains``, re-exported here so a copy of this
     module in another project only needs that one dependency.

The MX record check (Layer 4) is currently disabled — it was false-
positiving on real domains whose authoritative DNS was slow or
geo-restricted. Re-enable by setting ``MX_CHECK_ENABLED = True``
below. Bounces from the hosted email provider still catch truly
undeliverable addresses; this check was only ever a nice-to-have.
"""
from __future__ import annotations

from disposable_email_domains import blocklist as _DISPOSABLE_BLOCKLIST


# ── Blocklists ─────────────────────────────────────────────────────

PERSONAL_MAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.in", "yahoo.in", "ymail.com", "rocketmail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "aim.com",
    "protonmail.com", "proton.me", "pm.me",
    "zoho.com",
    "gmx.com", "gmx.us", "gmx.de",
    "mail.com", "mail.ru",
    "yandex.com", "yandex.ru",
    "rediffmail.com", "rediff.com",
    "tutanota.com",
})

DISPOSABLE_MAIL_DOMAINS: frozenset[str] = frozenset(_DISPOSABLE_BLOCKLIST)


# ── MX check (currently off) ───────────────────────────────────────

# Flip to True to re-enable the DNS MX record check that rejects
# domains without a mail server. Kept as a flag — not deleted — so the
# resolver code and reasoning survive if the check becomes useful
# again when we leave dev traffic behind.
MX_CHECK_ENABLED = False


def _domain_of(email: str) -> str:
    return email.strip().lower().rsplit("@", 1)[-1]


# ── Public API ─────────────────────────────────────────────────────


class EmailRejection(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def assert_work_email(email: str) -> None:
    """Raise :class:`EmailRejection` unless ``email`` looks like a real
    business inbox. Cheapest check first — bail on the first failure.
    """
    domain = _domain_of(email)
    if not domain or "." not in domain:
        raise EmailRejection("Enter a valid work email address.")
    if domain in PERSONAL_MAIL_DOMAINS:
        raise EmailRejection(
            "Please use your company email - personal addresses like "
            f"@{domain} are not accepted."
        )
    if domain in DISPOSABLE_MAIL_DOMAINS:
        raise EmailRejection("Disposable email services are not accepted.")
    # MX check intentionally skipped — see ``MX_CHECK_ENABLED`` note at
    # the top of this file for why. Hosted-provider bounces still catch
    # truly undeliverable addresses.
