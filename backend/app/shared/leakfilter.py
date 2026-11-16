"""The leak filter (build plan 7.1 / 18.5): one check for every free-text
field another party will read. It looks for ways to step around Corridor One
X: phone numbers, emails, links, messaging handles and company names.

    result = check("Call 98765 43210 for best rates")
    result.verdict   # Verdict.BLOCKED
    result.reasons   # ("phone number",)

* ``BLOCKED`` — refuse the text and tell the writer what to remove.
* ``REVIEW``  — keep it and show the reasons to a reviewer.
* ``PASS``    — nothing found.

Pattern rules only. They are tuned to catch plain attempts and digits written
as words; a classifier can sit behind the same function later.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass


class Verdict(str, enum.Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class LeakResult:
    verdict: Verdict
    reasons: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.verdict is Verdict.BLOCKED


_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "nil": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi, as traders write them in Latin script.
    "shunya": "0", "ek": "1", "do": "2", "teen": "3", "char": "4", "chaar": "4", "paanch": "5", "panch": "5",
    "chhe": "6", "chah": "6", "saat": "7", "aath": "8", "nau": "9",
}
_MULTIPLIERS = {"double": 2, "triple": 3}

#: A phone number is at least this many digits (UAE mobiles have nine).
_PHONE_MIN_DIGITS = 9

_EMAIL = re.compile(r"[a-z0-9._%+-]+\s*(@|\(at\)|\[at\]|\sat\s)\s*[a-z0-9-]+\s*(\.|\(dot\)|\[dot\]|\sdot\s)\s*[a-z]{2,}", re.I)
_URL = re.compile(
    r"(https?://|www\.)\S+|\b[a-z0-9-]{2,}\.(com|in|ae|net|org|co|io|biz|info|store|shop|online)\b(/\S*)?", re.I
)
_HANDLE = re.compile(r"(?<![a-z0-9])@[a-z0-9_.]{3,}", re.I)
#: Digits with the separators people put inside phone numbers.
_DIGIT_RUN = re.compile(r"\+?\d[\d\s().\-]{6,}\d")
_WORD = re.compile(r"[a-z]+|\d+", re.I)
_CHANNEL = re.compile(
    r"\b(whats\s*app|watsapp|wa\.me|telegram|we\s*chat|skype|signal|instagram|insta|facebook|linkedin|"
    r"call\s+(me|us)|contact\s+(me|us)|dm\s+(me|us)|ping\s+(me|us)|reach\s+(me|us))\b",
    re.I,
)
_COMPANY = re.compile(
    r"\b(pvt\.?\s*ltd|private\s+limited|limited|ltd|llp|llc|l\.l\.c|fzc|fze|fzco|inc|corp)\b\.?"
    r"|(&|\band)\s+(sons|co)\b\.?",
    re.I,
)


def check(text: str | None) -> LeakResult:
    """Classify one piece of free text. Empty text passes."""
    if not text or not text.strip():
        return LeakResult(Verdict.PASS)
    blocked: list[str] = []
    review: list[str] = []
    if _EMAIL.search(text):
        blocked.append("email address")
    if _URL.search(_EMAIL.sub(" ", text)):
        blocked.append("web address")
    if _HANDLE.search(_EMAIL.sub(" ", text)):
        blocked.append("messaging handle")
    if _has_phone_digits(text) or _has_spelled_number(text):
        blocked.append("phone number")
    if _CHANNEL.search(text):
        review.append("asks to be contacted directly")
    if _COMPANY.search(text):
        review.append("may name a company")
    if blocked:
        return LeakResult(Verdict.BLOCKED, tuple(blocked))
    if review:
        return LeakResult(Verdict.REVIEW, tuple(review))
    return LeakResult(Verdict.PASS)


def check_all(texts: dict[str, str | None]) -> dict[str, LeakResult]:
    """Check several named fields; only the ones that do not pass are returned."""
    results = {name: check(value) for name, value in texts.items()}
    return {name: r for name, r in results.items() if r.verdict is not Verdict.PASS}


def mentions(text: str | None, name: str | None) -> bool:
    """Does ``text`` contain the company name ``name``, ignoring case, spacing
    and the legal suffix? For the reviewer, who knows whose listing it is."""
    core = _COMPANY.sub(" ", name or "")
    words = [w.lower() for w in _WORD.findall(core) if len(w) > 2]
    if not text or not words:
        return False
    needle = r"\W*".join(re.escape(w) for w in words)
    return re.search(needle, text, re.I) is not None


def _has_phone_digits(text: str) -> bool:
    return any(sum(c.isdigit() for c in run.group()) >= _PHONE_MIN_DIGITS for run in _DIGIT_RUN.finditer(text))


def _has_spelled_number(text: str) -> bool:
    """Digits written as words, alone or mixed with figures: "nine eight 7
    six five double four three two one"."""
    digits = 0
    multiplier = 1
    spelled = False
    for token in _WORD.findall(text.lower()):
        if token in _MULTIPLIERS:
            multiplier = _MULTIPLIERS[token]
            continue
        if token in _DIGIT_WORDS:
            digits += multiplier
            spelled = True
        elif token.isdigit() and len(token) <= 4:
            digits += len(token) * multiplier
        else:
            digits, spelled = 0, False
        multiplier = 1
        if spelled and digits >= _PHONE_MIN_DIGITS:
            return True
    return False
