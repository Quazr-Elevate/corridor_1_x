# Test execution report

**Branch:** `work/pegan-2026-10-21`
**Date:** 2026-10-31
**Executor:** QA automation pass (Claude Code, pytest in-process harness)
**Scope:** KYB single-review branch — country-aware signup, admin
doc-requirement catalog, trader doc upload with slot binding, single-review
cascade (approve/reject), verified-biz re-edit auto-unverify.

## Summary

| Suite | Collected | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Existing project suite (`tests/test_*.py`) | 120 | 120 | 0 | 0 |
| New QA suite (`tests/qa/test_*.py`) | 42 | 42 | 0 | 0 |
| **Total** | **162** | **162** | **0** | **0** |

Wall time (whole suite, one invocation, `-q`): ~28 seconds on the dev laptop.
No tests were deselected and nothing was marked `xfail` / `skipif`.

## New QA suite — tests

Grouped by flow id (see `tests/qa/flows.md` for the flow catalogue).

### QA-100 — Country-aware signup (FLOW-100)

| Id | Case | Status |
| --- | --- | --- |
| QA-100.1 | Signup without `country` → 422 | PASS |
| QA-100.2 | Signup with invalid `country` (`"XX"`) → 422 | PASS |
| QA-100.3 | Signup accepts lowercase alpha-2 (`"in"` → `IN`) | PASS |
| QA-100.4 | Signup accepts alpha-3 (`"IND"` → `IN`) | PASS |

### QA-200 — Admin doc-requirement CRUD (FLOW-200)

| Id | Case | Status |
| --- | --- | --- |
| QA-200.1 | Full lifecycle: create → list → patch (display + mandatory flag) → deactivate → re-list with `includeInactive=1` | PASS |
| QA-200.2–6 | Slug regex — 5 parametrized rejections of invalid slugs (empty, caps, leading digit sans letter? → the regex allows, non-ascii, space, slash) | PASS |
| QA-200.7 | Duplicate `(country, slug)` → 409 | PASS |
| QA-200.8 | `country_code` and `slug` are immutable on PATCH | PASS |

### QA-300 — Trader doc upload + slot binding (FLOW-300)

| Id | Case | Status |
| --- | --- | --- |
| QA-300.1 | Upload with `required_doc_type_id` fills slot; response carries `requirementSlug` + `requirementDisplayName` | PASS |
| QA-300.2 | Replace-on-upload: second upload to same slot soft-deletes first | PASS |
| QA-300.3 | Upload without slot id → doc is "optional cert", `requirementSlug` null | PASS |
| QA-300.4 | Delete owned doc → 204; `/me/verification-docs` no longer lists it | PASS |

### QA-400 — Requirements for signed-in business (FLOW-400)

| Id | Case | Status |
| --- | --- | --- |
| QA-400.1 | `/me/verification-docs/requirements` returns slots for user's country only | PASS |
| QA-400.2 | Soft-deactivated catalog row disappears from trader view | PASS |
| QA-400.3 | Response includes `missing[]` for unfilled mandatory slots | PASS |

### QA-500 — Submit-for-verification gating (FLOW-500)

| Id | Case | Status |
| --- | --- | --- |
| QA-500.1 | Submit blocked while any mandatory profile field unfilled → 400 | PASS |
| QA-500.2 | Submit blocked while any mandatory doc slot empty → 400 | PASS |
| QA-500.3 | Submit succeeds when all mandatory profile + doc slots filled → 200 | PASS |
| QA-500.4 | Re-submit from `pending_verification` idempotent (no 409) | PASS |

### QA-600 — Single-review cascade (FLOW-600)

| Id | Case | Status |
| --- | --- | --- |
| QA-600.1 | Approve business → cascades: cert doc → approved | PASS |
| QA-600.2 | Reject w/ `failedItems=["legalName","doc:<slug>"]` → persists reason + items | PASS |
| QA-600.3 | Reject cascade: `doc:*` entries flip matching cert docs to `rejected` with same reason | PASS |
| QA-600.4 | Reject w/ empty `failedItems` → 422 (QA-F001 fix) | PASS |
| QA-600.5 | Reject w/ unknown bare key silently dropped; `doc:unknown_slug` persists | PASS |
| QA-600.6 | Reject an already-rejected business → 409 | PASS |
| QA-600.7 | Non-admin verify/reject → 401 | PASS |
| QA-600.8 | `/admin/verify/queue` carries `requirementSlug` + `requirementDisplayName` on each doc | PASS |

### QA-700 — Trader-side rejection state (FLOW-700)

| Id | Case | Status |
| --- | --- | --- |
| QA-700.1 | Rejected `doc:*` key re-enters `missing[]` so re-submit still gates on it | PASS |
| QA-700 (shared asserts in 600.2) | `rejectedItemLabels` keyed only by `doc:*`, value = display name | PASS |

### QA-800 — Verified biz re-edit → auto-unverify (FLOW-800)

| Id | Case | Status |
| --- | --- | --- |
| QA-800.1 | Edit mandatory profile field (`legalName`) → biz flips `verified` → `pending_verification`, `verifiedAt` nulled, old reject state cleared | PASS |
| QA-800.2 | Edit non-mandatory field (`websiteUrl`) → stays `verified` | PASS |
| QA-800.3 | Primary contact `fullName` change → flips | PASS |
| QA-800.4 | `tradePosition` change → flips | PASS |
| QA-800.5 | Approved cert doc stays `approved` across the flip (admin re-reviews with new data) | PASS |

### QA-900 — Admin verify-queue list filter (FLOW-900)

| Id | Case | Status |
| --- | --- | --- |
| QA-900.1 | Queue shows only `pending_verification`; excludes draft/verified/rejected | PASS |
| QA-900.2 | Pagination `limit`/`cursor` round-trips | PASS |

### Full test id → file map

- `test_country_signup.py` — QA-100.*
- `test_doc_requirements.py` — QA-200.*
- `test_trader_docs.py` — QA-300.*, QA-400.*, QA-500.*
- `test_single_review.py` — QA-600.*, QA-700.1
- `test_auto_unverify.py` — QA-800.*
- `test_admin_queue.py` — QA-900.*

## Existing suite notes

Two existing tests were adjusted this pass to accommodate the new
mandatory `country` field on signup:

- `tests/conftest.py::signup_and_login` — gained a `country: str = "IN"`
  default and now sends it in the signup body.
- `tests/test_auth.py::_complete` — same default added so existing auth
  tests don't 422 against the new validator.
- `tests/test_migration_0020.py` — pinned to `upgrade 0020_exchange_rates`
  because the head now points at `0024_*`.

These edits are **harness-only**; no app code was changed to make
existing tests pass. The three edits are visible in the diff.

## Bugs found and fixed during this pass

Found via the new QA suite. See `bug-report.md` for repro + root cause.

| Id | Area | Severity | Status |
| --- | --- | --- | --- |
| QA-F001 | Admin reject accepts empty `failedItems` | Low | Fixed |
| QA-F002 | Admin doc-requirements `includeInactive` camelCase ignored | Medium | Fixed |
| QA-F003 | Trader upload response missing requirement metadata | Medium | Fixed |

## Not executed in this pass

- UI E2E workflows were covered via the interactive browser pane in
  earlier sessions and documented in `qa_new_flows.md`. They are **not**
  codified as repeatable scripts in this suite.
- Load / stress testing — out of scope.
- Visual regression — out of scope.
- Cross-browser / cross-device — out of scope.

Reasons noted in `coverage-report.md`.
