# QA testing — Cor1x

How this suite is organised, how to run it, and where the reports live.

## Testing architecture

Three layers run against a **real** FastAPI app (no mocked internals):

1. **Existing project suite** (`backend/tests/test_*.py`) — unit + integration
   over auth, accounts, admin, catalog, csrf, docs, fx, migrations. Spins the
   ASGI app with an in-process throwaway SQLite DB (`backend/tests/conftest.py`
   creates a temp dir + env + schema per session).
2. **QA suite** (`backend/tests/qa/test_*.py`) — the new, flow-driven coverage
   added for the KYB single-review branch. Reuses the parent conftest's
   `client`, `admin_client`, `make_client`, `signup_and_login`,
   `fill_mandatory` fixtures. Adds its own helpers in
   `tests/qa/conftest.py` (`uniq`, `admin_add_requirement`,
   `upload_slot_doc`, `TINY_PNG`).
3. **E2E workflows** — browser-driven, covered interactively via the
   in-app browser pane during the session; results documented in
   `qa_new_flows.md`. Not currently codified as repeatable scripts (would
   need a Playwright/Cypress install we deliberately didn't add).

The two pytest layers run in-process — no HTTP, no live backend needed, no
Postgres, no S3 storage, no SMTP. Everything is fakes/local defaults from
the conftest env.

## Prerequisites

- Python 3.12
- `backend/.venv` with the backend deps installed (per the project README).
- `pytest`, `pytest-asyncio`, `httpx` — install into the same venv:

```bash
cd backend
./.venv/Scripts/python.exe -m pip install pytest pytest-asyncio httpx
```

## Environment configuration

The suite overrides envs in `tests/conftest.py` before importing the app:
`DATABASE_URL` → SQLite in a temp dir, admin creds known to the suite
(`admin@cor1x.test` / `admin-pass-123`), email/sms providers set to
`console`, S3/SMTP left off. **Nothing in `backend/.env` is touched.**

## Run commands

```bash
cd backend

# Everything (existing + QA)
./.venv/Scripts/python.exe -m pytest tests/ -q

# QA only
./.venv/Scripts/python.exe -m pytest tests/qa/ -q

# One test by id (pytest nodeid)
./.venv/Scripts/python.exe -m pytest tests/qa/test_single_review.py::test_approve_cascades_to_cert_docs -v

# Regression — the whole suite with short tracebacks on failure
./.venv/Scripts/python.exe -m pytest tests/ --tb=short

# After an app change, before merge: full suite + fail-fast
./.venv/Scripts/python.exe -m pytest tests/ -x
```

The suite completes in ~30 seconds on a laptop.

## E2E workflows

The three critical end-to-end workflows (admin reject → trader fix →
resubmit, verified-biz mandatory edit auto-unverify, admin seed catalog
row → trader sees it instantly) have been executed in the browser pane
and documented. To re-run manually:

1. `./.venv/Scripts/python.exe -m uvicorn --app-dir backend app.main:app --reload --port 8000`
2. `cd frontend && npm run dev`
3. `./.venv/Scripts/python.exe -m scripts.seed_review_fixtures` (seeds
   three fully-filled trader fixtures)
4. Log in as `admin@cor1x.local / admin123` and `review1@review.cor1x.co /
   TestPass123!` to drive the flows.

See `qa_new_flows.md` (shipped artifact from the earlier interactive
session) for recorded screenshots and step-by-step evidence.

## Reports

- `test-execution-report.md` — tests run, pass/fail counts, timings
- `bug-report.md` — defects found with repro + root cause + fix status
- `coverage-report.md` — modules, APIs, flows, roles with explicit "not
  tested" sections
- `flows.md` (in `tests/qa/`) — business flow catalog with trace IDs the
  tests reference

## Known honest gaps

The following are **intentionally not covered** by this pytest suite and
noted in `coverage-report.md`:

- Rate limiting (per-IP, per-email) — needs burst traffic; existing
  env disables the real limiter in-test.
- Email delivery — `EMAIL_PROVIDER=console` in-test; no SMTP exercised.
- S3 storage — `backend/app/integrations/storage/s3.py` not loaded.
- Browser race conditions (tab-flip in Docs lane) — browser-driven;
  verified in prior interactive session.
- Live file previews (image / PDF) in the view dialog — browser-driven.

## Testing conventions

- Every new test gets a `QA-NNN.N` id in a comment or docstring and
  references its `FLOW-NNN` in `tests/qa/flows.md`.
- Email addresses use `uniq("qa<flow>")` so parallel runs never collide.
- Doc requirement slugs use `uniq("slug").replace("-", "_")` to satisfy
  the catalog's `^[a-z0-9][a-z0-9_-]{0,39}$` regex and remain unique.
- No tests assume starting-state DB fixtures — each test creates what it
  needs. The parent conftest's `_clean` autouse fixture truncates between
  tests.
- No tests silently skip. If a feature can't be exercised in this harness,
  it's listed in `coverage-report.md` with a reason.
