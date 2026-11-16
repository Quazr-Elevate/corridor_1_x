"""Notification template lint (CX-088, build plan 19.1): a template must not
be able to print a real name, and mail leaves from the platform's address
only."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from jinja2 import Environment, meta

from app import notifications
from app.models import VAULT_COLUMNS

TEMPLATES = Path(notifications.__file__).resolve().parent / "templates"

#: Every variable a template may use. ``first_name`` and ``email`` are the
#: recipient's own; nothing here can hold another party's identity. A new
#: variable is added here on purpose, in review.
ALLOWED_VARIABLES = {
    "account_url", "cert_type", "code", "dashboard_url", "device", "email", "first_name", "reason",
    "reset_url", "subject", "support_email", "valid_minutes", "when",
}
#: Names that would carry a company's or a counterparty's identity.
FORBIDDEN = set(VAULT_COLUMNS) | {
    "business_name", "company_name", "full_name", "phone", "seller", "buyer", "counterparty", "identity",
    "business", "user",
}


def _variables(path: Path) -> set[str]:
    return meta.find_undeclared_variables(Environment().parse(path.read_text()))


def test_templates_use_only_allowed_variables():
    files = sorted(TEMPLATES.glob("*.html")) + sorted(TEMPLATES.glob("*.txt"))
    assert len(files) >= 10, "No templates found; the lint would pass on nothing."
    problems = []
    for path in files:
        used = _variables(path)
        if used & FORBIDDEN:
            problems.append(f"{path.name}: identity variable {sorted(used & FORBIDDEN)}")
        if used - ALLOWED_VARIABLES:
            problems.append(f"{path.name}: unlisted variable {sorted(used - ALLOWED_VARIABLES)}")
    assert not problems, "\n".join(problems)


def test_no_template_reaches_into_an_object():
    """``{{ user.email }}`` would get past a variable list, so attribute and
    item access are not allowed at all: templates take plain values."""
    access = re.compile(r"{{[^}]*\b[a-z_]+\s*(\.|\[)\s*[a-z_'\"]")
    offenders = [p.name for p in TEMPLATES.iterdir() if p.is_file() and access.search(p.read_text())]
    assert offenders == []


def test_the_lint_catches_what_it_is_for(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("Your counterparty is {{ legal_name }} ({{ deal_ref }}).")
    used = _variables(bad)
    assert used & FORBIDDEN == {"legal_name"} and used - ALLOWED_VARIABLES == {"legal_name", "deal_ref"}


def test_mail_is_sent_from_the_platform_address_only():
    """No send function may choose the sender or a reply address: both come
    from configuration (EMAIL_FROM, EMAIL_REPLY_TO)."""
    source = inspect.getsource(notifications)
    assert "from_address" not in source and "reply_to" not in source and "from_name" not in source
    assert set(inspect.signature(notifications._send).parameters) == {"to", "subject", "template", "context"}
