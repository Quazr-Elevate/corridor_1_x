# Coverage report

Scope: the KYB single-review branch on `work/pegan-2026-10-21`. This
report is **honest about gaps** — it lists what's tested and what isn't,
and gives a reason for each gap. "100% coverage" is **not** claimed.

## Features and flows

| Feature / flow | API tested | E2E tested | Gaps |
| --- | --- | --- | --- |
| Signup w/ country (FLOW-100) | ✅ QA-100.* | ✅ interactive session | None |
| Admin doc-req CRUD (FLOW-200) | ✅ QA-200.* | ✅ interactive session | Soft-delete + reactivate not E2E-automated |
| Trader doc upload + slot (FLOW-300) | ✅ QA-300.* | ✅ interactive session | Live PDF/image preview rendering is browser-only (see §Not covered) |
| Trader requirements list (FLOW-400) | ✅ QA-400.* | ✅ interactive session | None |
| Submit gating (FLOW-500) | ✅ QA-500.* | ✅ interactive session | None |
| Single-review cascade (FLOW-600) | ✅ QA-600.* | ✅ interactive session | None material |
| Trader rejection state (FLOW-700) | ✅ QA-700.1 (via 600.2) | ✅ interactive session | None |
| Verified-biz re-edit auto-unverify (FLOW-800) | ✅ QA-800.* | ⚠️ interactive partial | Full UI journey only driven once in-session |
| Admin verify queue filter (FLOW-900) | ✅ QA-900.* | ✅ interactive session | None |

## Backend module coverage (new / modified in this branch)

| Module | Lines of concern | Tested? |
| --- | --- | --- |
| `app/modules/admin/doc_requirements.py` | CRUD, country filter, immutability, slug regex | ✅ QA-200.* |
| `app/modules/admin/service.py` (reject/verify) | state machine + cascade + items persistence | ✅ QA-600.* |
| `app/modules/verification/router.py` upload+list | slot binding, replace-on-upload, metadata attach | ✅ QA-300.*, QA-F003 regression |
| `app/modules/verification/schemas.py` doc_to_out | requirementSlug / requirementDisplayName | ✅ QA-300.1, QA-600.8 |
| `app/modules/auth/service.py` signup country | normalization (alpha-2/3, lowercase) | ✅ QA-100.* |
| `app/modules/accounts/service.py` auto-unverify | mandatory field diff → flip | ✅ QA-800.* |
| `app/models/business_document_requirement.py` | SQL constraints + unique(country,slug) | ✅ QA-200.7 |
| `alembic/versions/0021_country_doc_requirements.py` | up / down | ⚠️ `tests/test_migrations.py` covers up to 0020; 0021–0024 not individually tested |
| `alembic/versions/0022_seed_doc_requirements.py` | seed only | ⚠️ not tested in-isolation (same reason) |

## Frontend coverage

| Component | Change | Tested? |
| --- | --- | --- |
| `frontend/components/admin/BusinessReviewView.tsx` | Show every mandatory cert; swapped headline/sub typography | ⚠️ Verified by eye in interactive session; no component test |
| `frontend/app/admin/doc-requirements/*` | New admin screen for doc-requirement CRUD | ⚠️ Verified by eye; no component test |
| `frontend/components/account/RequiredDocsBlock.tsx` | New trader-facing docs block | ⚠️ Verified by eye |
| `frontend/lib/adminApi.ts` / `api.ts` | New endpoints + camelCase param plumbing | ⚠️ Indirectly via browser session (hits same URL/params as pytest) |

Frontend has no component-level testing framework configured in-repo.
Adding Vitest + React Testing Library would be a separate branch of
work; not in scope for this QA pass.

## Role coverage

| Role | Coverage |
| --- | --- |
| Admin (platform operator) | ✅ CRUD, queue, verify, reject, state checks |
| Trader (business owner) | ✅ signup, onboarding, docs upload, submit, resubmit, auto-unverify |
| Unauthenticated | ⚠️ 401 tested for admin endpoints only (QA-600.7); public endpoints not exhaustively tested in this pass |
| Reviewer (if separate from admin) | ❌ no separate reviewer role exists in the current data model — admin IS reviewer |

## Not covered — with reasons

### Not tested in this pass; recommended for a later pass

1. **Rate limiting.** `app/core/rate_limit.py` is bypassed in the test
   env (`conftest.py` disables `redis` backend). To exercise rate limits
   you need either a running Redis + repeated bursts, or an in-memory
   backend swap-in — neither is set up today.

2. **Email delivery.** `EMAIL_PROVIDER=console` in-test, so every notice
   is logged, not sent. No SMTP, no DMARC, no bounce handling. Current
   suite only asserts "a 6-digit code appears in captured log output"
   (via `code_from_email` helper); it does not test subject lines,
   templates, or HTML rendering.

3. **S3 storage.** `app/integrations/storage/s3.py` is not loaded when
   `STORAGE_BACKEND=local`. Doc uploads land under
   `backend/.data/uploads/` in-test. Everything about S3 ACL, presigned
   URLs, and signature expiry is **untested here**.

4. **File-type sniffing.** The upload endpoint accepts the UploadFile's
   content-type as-is. We didn't test what happens for `.exe` renamed
   to `.pdf`, oversize bombs, or SVG with embedded script. The
   `MAX_DOC_BYTES` guard is tested indirectly (QA-300.* uses tiny PNGs).

5. **Browser race conditions.** The Docs lane re-tab-flip after an
   `includeInactive` toggle was manually verified; no automated proxy
   exists. Would need Playwright.

6. **Visual regression.** No pixel-diff baseline exists.

7. **Accessibility (a11y).** No axe-core / lighthouse run.

8. **Cross-locale.** Only `country=IN` was exercised end-to-end. US / UK
   / ARE catalog shapes seeded by `0022_seed_doc_requirements.py` are
   assumed correct by inspection; no QA test asserts the seed content.

9. **Concurrent submissions.** Two tabs submit-verification at the same
   moment — behavior is the DB's uniqueness guarantee, not asserted.

10. **Long docs lists.** No test uses >5 docs per business. Pagination
    assumptions in `/admin/verify/queue` tested at `limit=1` only.

### Not applicable in this harness

- **Postgres-specific features** (JSONB operators, generated columns):
  the test env uses SQLite via `aiosqlite`. The computed column
  `verification_rejected_item_labels` is defined on the model but is
  SQLite-friendly (plain Python `@property` under the hood). Postgres
  behavior is **not re-verified by pytest here**; the dev / staging
  environment runs on Postgres and is the authority.

- **Alembic 0021–0024 migrations as their own test cases.** The
  pre-existing `test_migration_0020.py` is pinned to that revision as a
  compatibility test. We did not add a dedicated test per new revision
  because the schema under test is created directly from
  `app.models.*` metadata in `conftest.py`; the migrations are
  exercised in dev and staging separately. Flagged here honestly rather
  than claimed as "tested".

## What a "finished" coverage story would still need

In rough priority order, to turn this honest pass into a durable
regression safety net:

1. Playwright E2E suite codifying the 3 interactive E2E flows.
2. Vitest + RTL for the new frontend components (BusinessReviewView,
   admin/doc-requirements page, RequiredDocsBlock).
3. Dedicated migration tests for 0021 → 0024.
4. Postgres-mode CI job (currently only SQLite in-test).
5. Rate-limit regression tests with an in-memory limiter backend.
6. Upload hardening tests (content-type spoof, oversize, SVG-script).
7. Fixtures asserting the shipped seed catalog content per country.

None of these are blockers for the KYB single-review branch landing;
they are the next-step QA work.
