# Code style: writing like this team

The test for every line: **would a senior engineer reviewing this PR assume a
careful colleague wrote it?** Not "is it correct" — correct code can still read
as pasted, padded or generated. This codebase reads as written by people who
know the domain and respect the reader. New code must be indistinguishable from
the best of what's already here.

The good examples below are quoted from the repository. Match them.

## Contents

- [Naming](#naming)
- [Functions](#functions)
- [Comments](#comments)
- [Docstrings](#docstrings)
- [Error messages](#error-messages)
- [Logging](#logging)
- [Python conventions](#python-conventions)
- [Tells to remove before you commit](#tells-to-remove-before-you-commit)
- [Commit messages](#commit-messages)
- [Pull requests](#pull-requests)
- [Docs and customer-facing text](#docs-and-customer-facing-text)

## Naming

Names come from the domain and say exactly what the thing is.

| Ours | Not |
|---|---|
| `list_own_products`, `reveal_contact`, `store_photo` | `get_data`, `handle_request`, `process_item` |
| `visible_products_clause` | `filter_query`, `build_conditions` |
| `commit_or_conflict` | `safe_commit`, `commit_helper` |
| `REVEAL_MAX_PER_WINDOW`, `MAX_PHOTO_BYTES` | `LIMIT`, `MAX`, `CONFIG_VALUE` |
| `ADMIN_REVEAL` (a `RateLimitRule`) | `rate_limit_rule_1` |
| `CanReviewKyb`, `CanViewSensitive` | `AdminDep`, `PermissionChecker` |
| `uniqueness.py`, `lockout.py`, `sessions.py` | `utils.py`, `helpers.py`, `common.py`, `manager.py` |

- Use the business's words: *listing*, *reveal*, *KYB entry*, *reviewer*,
  *verified business*. When the code and the plan use different words for the
  same thing (`products` / *listings*), keep the code's word and don't introduce
  a third.
- Booleans read as questions: `is_verified`, `has_open_claim`.
- Functions are verbs, values are nouns. No type names inside names
  (`product_list`, `user_dict`).
- A file named `utils` or `helpers` is a sign the code hasn't found its home yet.
  Put the function next to what it serves.

## Functions

- One job, named for that job. If the docstring needs "and", it's probably two.
- Service signatures run `(db, principal, payload or ids)`, in that order, every time.
- Early returns and guard clauses over nesting: validate, refuse, then do the work.
- Stay close to the shape around you. A 40-line service function that reads
  top to bottom beats eight 5-line functions that make the reader jump.
- No abstraction with a single implementation. No base class, factory, strategy
  or registry until there's a second real case.
- No flag arguments that switch between two behaviours. Write two functions.

## Comments

A comment earns its place by saying something the code can't: **why**, a
constraint, a consequence, a trap, or a pointer to the document that decided it.
Most lines need none.

Good, from the repo:

```python
# A concurrent sign-in won the one-active-session index; retry once.
# Pre-checks before any mutation (avoids autoflush surprises).
# Issuing a new code invalidates older unused ones.
# Only with DEBUG=true (local dev) — never in production.
# Cheap free-text; move to tsvector / FTS5 past ~10k products.
# price_per_unit ÷ rate(currency) — for cross-currency filtering only;
# the seller's price is never changed. NULL when unpriced / no rate.
# KYB entries go with the business (data minimisation; frees the
# GSTIN / PAN for a fresh registration). Files are removed after commit.
```

Every one says why, or what would go wrong without it, or when it stops being true.

Avoid:

```python
# Get the product                         ← says what the next line already says
product = await get_product(db, product_id)

# Added validation for price range        ← narrates the change; that's the commit message's job
# Updated to fix the bug                   ← history belongs in git
# Note: this is important                  ← says nothing
# TODO: implement later                    ← ship it or open a tracker row
# Loop through each item and process it    ← the code is right there
```

A `TODO` is allowed only with a tracker ID and a reason:
`# TODO(CX-009): in-memory limiter resets per process; Redis in Phase B.`

## Docstrings

One line that states the contract and the non-obvious part. Continue onto a
second line only when a real constraint needs it.

```python
"""The business's listings (not deleted), newest first."""
"""Storage key for a served photo filename, or None if malformed."""
"""Validate by magic bytes, store, return the public relative URL."""
"""Soft delete (the listing leaves the market; reveals keep their history)."""
"""DB-backed (survives restarts, shared across workers): at most
REVEAL_MAX_PER_WINDOW *new* reveals per buyer BUSINESS per hour."""
```

Not this:

```python
def list_own_products(db: AsyncSession, user: User) -> list[Product]:
    """
    List products.

    This function retrieves a list of products belonging to the user's business.

    Args:
        db (AsyncSession): The database session.
        user (User): The current user.

    Returns:
        list[Product]: A list of products.
    """
```

The signature already says the types. The docstring's job is what the
signature can't: *not deleted*, *newest first*.

**Module docstrings** say what the module holds and, for routers, list the
routers and their prefixes (see `catalog/router.py`). **Migration docstrings**
follow the shape in `architecture.md`. **Model docstrings** state the rule that
governs visibility or lifetime (see `Product`, `ContactReveal`).

## Error messages

Errors are written for the person who will read them: usually a trader, sometimes
a reviewer. A message says what's wrong and what to do, in a full sentence that
ends with a period.

From the repo:

```python
"Enter the number or upload the document."
"A rejection reason is required so the business knows what to fix."
"Corridor One X doesn't onboard businesses from that country yet."
"Keep at least one active super admin."
"New password must be different from the current one."
"Get your business verified before revealing seller contact details."
"This is your own business's listing — nothing to reveal."
```

Rules:
- Say it the way a helpful colleague would. Use "Enter…", "Keep…", "Get…", not
  "Invalid input" or "Validation error".
- No internal names: no table, column, enum, exception class or HTTP jargon.
- No blame and no exclamation marks.
- Name limits concretely: "Document name is too long (150 characters max)."
- The product is "Corridor One X" in user-facing text.
- Security errors stay generic on purpose: "Invalid email or password." for both
  a wrong password and an unknown email. Never reveal whether an account exists.
- For a state conflict, name both states: "A published listing can't be moved to draft."

## Logging

Structured `event_name key=value` lines with lazy `%s` formatting, so values are
only formatted when the line is emitted:

```python
log.warning("csrf_blocked method=%s path=%s origin=%s", ...)
log.info("rate_limited rule=%s retry_after=%s", ...)
log.warning("domain_error status=%s detail=%r", ...)
log.exception("unhandled_error type=%s", ...)
log.warning("fx: provider %s failed: %s", ...)      # integrations prefix their area
```

- `snake_case` event names that a person can grep for.
- `info` for notable normal events, `warning` for refused or degraded,
  `exception` only inside an `except` that's handling a real failure.
- Never log passwords, codes, tokens, KYB numbers, file contents, full IPs,
  email bodies, or any field from the identity vault. Log IDs, not people.
- No `print()`. No emoji. No "Successfully did X!" lines.

## Python conventions

- `from __future__ import annotations` at the top of every module, as the codebase does.
- Type hints on every function signature; SQLAlchemy 2.0 `Mapped[...]` and `mapped_column` on models.
- Module-level constants in `UPPER_CASE` with units in the name or a comment:
  `MAX_PHOTO_BYTES`, `window_sec=60 * 60`.
- Catch the exception you expect (`IntegrityError`, `ValueError`), handle it,
  and re-raise what you don't. Never `except Exception: pass`, never a bare `except:`.
- `Decimal` for prices today and integer minor units for ledger money (M5). Never `float` for money.
- UTC everywhere (`core/time.py`, `UTCDateTime`); convert for display only on the client.
- f-strings for user-facing messages; lazy `%s` for logs.
- Imports grouped stdlib / third-party / `app`, with absolute `app.` imports.

## Tells to remove before you commit

These mark code as generated and unreviewed. Read your diff once looking only
for them.

| Tell | Instead |
|---|---|
| Comments narrating each line, or the change itself | Delete them; keep only the *why* |
| `Args:` / `Returns:` blocks repeating the signature | A one-line contract docstring |
| `try: ... except Exception as e: log.error(e)` around everything | Let real errors propagate to the central handler; catch only what you can handle |
| Defensive `if x is not None` on values that can't be `None` | Trust the types; check at the boundary once |
| A new helper module, base class or config option "for flexibility" | Write the direct code; abstract on the second real use |
| Placeholder values, fake data, `pass  # implement`, `NotImplementedError` left in | Finish it, or don't merge it |
| Reformatting or renaming untouched code in the same diff | A separate PR, if at all |
| Emoji, decorative separators, ASCII banners | Plain text |
| "robust", "seamless", "comprehensive", "leverage", "enhance", "utilize", "ensure" in prose | Say the concrete thing: "retries twice", "rejects unknown fields" |
| Exhaustive bullet lists in commit messages ("- Added X / - Updated Y" for every file) | What changed and why, grouped by area |
| Over-hedged prose: "This should hopefully help to potentially…" | State it, or say what's unverified |
| Tests that only assert the status code | Assert the body, the side effect and the refusal |
| Identical boilerplate repeated across new files | Match the module's real pattern, not a template |

The section-divider comments the routers already use
(`# ── /products ──────`) are part of the house style. Keep them where a file
already has them; don't add banners elsewhere.

## Commit messages

Subject: `Area: what changed, the specifics`. Under ~72 characters, no trailing
period, describing the result rather than the activity. From the history:

```
Phase A identity & access: named admins + roles, one-device sessions, lockout
Cookies: decouple cross-site policy from DEBUG (CROSS_SITE_COOKIES)
Railway: pin frontend healthcheck to /login (200), not a redirect
PWA: network-first HTML so deploys aren't masked by the SW cache
```

With a tracker row, lead with its ID: `CX-067 Uploads: strip EXIF and GPS on write`.

The body, when the change isn't trivial: grouped by Backend / Frontend / Docs,
written as short sentences or dashes with concrete facts (migration names,
limits, behaviour), ending with the test count:

```
Backend (migration 0024_identity_access):
- admin_users (super_admin | reviewer) with a permission map; every /admin
  route declares one permission (route-matrix test).
- Lockout for users and admins: 5 fails -> 15 min, then 30 min, then
  support-only unlock.

Docs: data model 0024, security review Phase A status. Tests: 238 passing.
```

Not these, which are also in the history and are what to avoid:
`update the proxies`, `updating proxy issue`, `update build`.

## Pull requests

```markdown
CX-071 Listing review workflow

**Row:** CX-071 · M1 · S3 · plan 3.7

**What changes**
Two or three sentences: the behaviour before, the behaviour after.

**Done when**
- [x] products.status Draft / Under review / Published / Rejected — migration 0026, CheckConstraint
- [x] Only Published in the market — test_listing_needs_review_before_market
- [ ] …each line from the tracker, with its evidence

**Security** (references/security.md checklist)
- [x] Owner-scoped queries; stranger 404 — test_…
- [x] New route declares CanReviewListings; route-matrix test passes
- n/a Uploads — no file handling in this change

**Migration** 0026_listing_review: backfills existing verified listings to published. Reversible.

**Not in this PR** Anything noticed but left out, with its new tracker row.

**Tests** 241 passing (+3).
```

## Docs and customer-facing text

`06_feature_catalogue.md` is written for Corridor One X's customers: plain
sentences about what they can do, never how it's built.

> ✅ Every listing is reviewed by Corridor before it appears in the market; edits are re-reviewed while the live version stays up.

Not: "Implemented a robust state-machine-driven listing moderation pipeline."

Engineering docs (`04`, `05`, `07`, milestone designs) are direct and specific:
tables over paragraphs, numbers over adjectives, and the reason next to the rule.
