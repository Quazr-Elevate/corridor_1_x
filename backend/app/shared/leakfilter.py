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
_TLD = r"(com|in|ae|net|org|co|io|biz|info|store|shop|online)"
_URL = re.compile(
    r"(https?://|www\.)\S+|\b[a-z0-9-]{2,}\." + _TLD + r"\b(/\S*)?"
    # The dot written out or boxed: "acmeagro dot com", "acmeagro (.) in".
    r"|\b[a-z0-9-]{2,}\s*(\(\s*\.\s*\)|\[\s*\.\s*\]|\(dot\)|\[dot\]|\sdot\s)\s*" + _TLD + r"\b",
    re.I,
)
_HANDLE = re.compile(
    r"(?<![a-z0-9])@[a-z0-9_.]{3,}"
    # A platform's short name and a colon in front of a handle: "IG: acmeagro".
    r"|\b(ig|fb|tg|wa|insta|telegram|snap)\s*[:\-]\s*[a-z0-9_.]{3,}",
    re.I,
)
#: Digits with the separators people put inside phone numbers.
_DIGIT_RUN = re.compile(r"\+?\d[\d\s().\-/]{6,}\d")
#: A unit right after a run of numbers makes it a list of quantities
#: ("1000 2000 5000 MT"), not a phone number.
_UNIT_AFTER = re.compile(
    r"\s*(%|mt|kg|kgs|g|gm|tons?|tonnes?|quintals?|qtl|bags?|mm|cm|days?|weeks?|months?|years?|"
    r"usd|inr|aed|rs|containers?|fcl|lots?|pcs)\b",
    re.I,
)
#: Single letters typed apart to dodge a word check: "W h a t s A p p".
_SPACED_LETTERS = re.compile(r"\b(?:[a-z]\s){3,}[a-z]\b", re.I)
_WORD = re.compile(r"[a-z]+|\d+", re.I)
_CHANNEL = re.compile(
    r"\b(whats\s*app|watsapp|wa\.me|telegram|we\s*chat|skype|signal|instagram|insta|facebook|linkedin|"
    r"call\s+(me|us)|contact\s+(me|us)|dm\s+(me|us)|ping\s+(me|us)|reach\s+(me|us))\b",
    re.I,
)
#: Suffixes that only ever end a company name.
_COMPANY = re.compile(
    r"(?i:\b(pvt\.?\s*ltd|private\s+limited|ltd|llp|llc|l\.l\.c|fzc|fze|fzco)\b\.?)"
    r"|(?i:(&|\band)\s+(sons|co)\b\.?)"
    # Words that are also ordinary English ("limited stock") count only after
    # a capitalised word: "Kaveri Foods Limited", "Acme Inc".
    r"|\b[A-Z][A-Za-z]{1,40}\s+(Limited|LIMITED|Inc|INC|Corp|CORP|Corporation)\b\.?",
)


def check(text: str | None, own_name: str | None = None) -> LeakResult:
    """Classify one piece of free text. Empty text passes. ``own_name`` is
    the writer's own legal name: naming it is refused (see :func:`names`)."""
    if not text or not text.strip():
        return LeakResult(Verdict.PASS)
    blocked: list[str] = []
    review: list[str] = []
    # Checked twice: as written, and with letters typed apart closed up.
    variants = (text, _squeeze(text))
    if any(_EMAIL.search(t) for t in variants):
        blocked.append("email address")
    if any(_URL.search(_EMAIL.sub(" ", t)) for t in variants):
        blocked.append("web address")
    if any(_HANDLE.search(_EMAIL.sub(" ", t)) for t in variants):
        blocked.append("messaging handle")
    if _has_phone_digits(text) or _has_spelled_number(text):
        blocked.append("phone number")
    if names(text, own_name):
        blocked.append("company name")
    if any(_CHANNEL.search(t) for t in variants):
        review.append("asks to be contacted directly")
    if _COMPANY.search(text):
        review.append("may name a company")
    if blocked:
        return LeakResult(Verdict.BLOCKED, tuple(blocked))
    if review:
        return LeakResult(Verdict.REVIEW, tuple(review))
    return LeakResult(Verdict.PASS)


def check_all(texts: dict[str, str | None], own_name: str | None = None) -> dict[str, LeakResult]:
    """Check several named fields; only the ones that do not pass are returned."""
    results = {name: check(value, own_name) for name, value in texts.items()}
    return {name: r for name, r in results.items() if r.verdict is not Verdict.PASS}


def mentions(text: str | None, name: str | None) -> bool:
    """Does ``text`` contain the company name ``name``, ignoring case, spacing
    and the legal suffix? For the reviewer, who knows whose listing it is."""
    words = _core_words(name)
    if not text or not words:
        return False
    needle = r"\W*".join(re.escape(w) for w in words)
    return re.search(needle, text, re.I) is not None


def names(text: str | None, own_name: str | None) -> bool:
    """Does the writer name their own company? Only for names of two or more
    words once the suffix is gone: a one-word name ("Basmati Pvt Ltd") is
    too often an ordinary trade word, so that case is left to the reviewer."""
    return len(_core_words(own_name)) >= 2 and mentions(text, own_name)


def _core_words(name: str | None) -> list[str]:
    core = re.sub(r"\b(pvt\.?\s*ltd|private\s+limited|limited|ltd|llp|llc|l\.l\.c|fzc|fze|fzco|inc|corp)\b\.?", " ",
                  name or "", flags=re.I)
    return [w.lower() for w in _WORD.findall(core) if len(w) > 2]


def _squeeze(text: str) -> str:
    """Close up letters typed apart, and a dot with spaces on both sides
    ("w w w . acmeagro . in"); a sentence's full stop has no space before it."""
    text = _SPACED_LETTERS.sub(lambda m: m.group().replace(" ", ""), text)
    return re.sub(r"(?<=\w)\s+\.\s+(?=\w)", ".", text)


#: Dates are digit runs too ("01/12/2026 - 15/12/2026"); they are taken out first.
_DATE = re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](\d{4}|\d{2})\b|\b\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}\b")


def _has_phone_digits(text: str) -> bool:
    text = _DATE.sub(" ; ", text)
    for run in _DIGIT_RUN.finditer(text):
        if sum(c.isdigit() for c in run.group()) < _PHONE_MIN_DIGITS:
            continue
        if _is_quantity_list(run.group()) and _UNIT_AFTER.match(text, run.end()):
            continue
        return True
    return False


def _is_quantity_list(run: str) -> bool:
    """Two or more short numbers in rising order, the way quantities and
    pack sizes are listed. A phone number split into groups doesn't rise."""
    groups = [int(g) for g in re.findall(r"\d+", run)]
    return (
        len(groups) >= 2
        and all(len(str(g)) <= 6 for g in groups)
        and all(a < b for a, b in zip(groups, groups[1:]))
    )


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
