# Cor1x Backend

FastAPI + SQLAlchemy 2.0 (async) + Alembic. **SQLite for local dev, Postgres
(Railway) in production** — same code, selected by `DATABASE_URL`.

Cor1x is a verified B2B agri marketplace. The **business** is the main
entity: a person signs up with a work email (6-digit code on the same screen),
which creates their business (`draft`) and makes them its `owner`. They fill
the Passport (person + company fields), press **Send for verification**, and an
admin approves or rejects the business. Listings of verified businesses appear
in the market; a verified business can reveal another verified business's
contact on a product. Full schema: `docs/04_data_model.md`.

## Architecture

```
backend/
├── app/
│   ├── main.py                 # create_app(): logging, integrations, middleware, handlers, routers
│   ├── core/                   # app-wide plumbing (no business rules)
│   │   ├── config.py           # Settings (env / .env), BACKEND_DIR anchoring
│   │   ├── db.py               # async engine, SessionLocal, get_db, ping_db
│   │   ├── security.py         # bcrypt, signed session/admin tokens, cookie policy, AdminEmail dep
│   │   ├── errors.py           # DomainError hierarchy + central exception handlers ({"detail": ...})
│   │   ├── logging.py          # key=value / JSON logging, X-Request-ID middleware + access log
│   │   └── time.py             # utcnow(), ensure_aware()
│   ├── integrations/           # reusable, app-agnostic adapters (ABC + dev provider + real providers)
│   │   ├── email/              # console | resend | brevo — async, retry with backoff
│   │   ├── sms/                # console | msg91 — send_sms / send_otp / verify_otp (not wired yet)
│   │   ├── storage/            # LocalStorage | S3Storage (skeleton); magic-byte file type sniffing
│   │   ├── fx/                 # USD exchange rates: frankfurter | fawazahmed0 | static, fallback chain + AED peg
│   │   └── lookups/            # India Post pincode, Razorpay IFSC
│   ├── notifications/          # Jinja2 templates (html + txt) + typed send_* functions
│   ├── ratelimit/              # RateLimiter + in-memory sliding window backend + FastAPI deps
│   ├── modules/                # feature slices: router.py (thin HTTP) / schemas.py / service.py
│   │   ├── auth/               # signup (email code), login, change password, sessions, CurrentUser dep
│   │   ├── accounts/           # /me, /onboarding/*, completion predicates, uniqueness rules
│   │   ├── verification/       # mandatory-field rules, KYB document upload/download
│   │   ├── catalog/            # /products, /public/*, contact reveal, /uploads/products/<file>
│   │   ├── fx/                 # rates table reads, refresh + price_usd upkeep, /public/fx/rates, background task
│   │   ├── admin/              # auth.py, dashboard.py, users.py, docs.py (+ audit trail)
│   │   ├── lookups/            # /pincode/{p}, /ifsc/{code}
│   │   └── health/             # /health (DB ping)
│   ├── models/                 # SQLAlchemy models (UTCDateTime → aware datetimes on every dialect)
│   └── shared/                 # CamelModel + typed fields, normalizers, ISO countries, safe file responses
├── alembic/                    # migrations (0001–0017 Postgres-only, 0018+ portable)
├── scripts/
│   ├── init_local_db.py        # fresh SQLite DB: create_all + alembic stamp head
│   ├── seed_demo.py            # verified demo sellers + products (with stored placeholder photos)
│   └── seed_test_users.py      # 5 accounts across every business verification state
└── tests/                      # pytest + httpx against the ASGI app on a temp SQLite DB
```

Rules of the road:

* Routers are thin: parse input, call a service, shape the response.
* Services raise `app.core.errors.*` (`BadRequest`, `Conflict`, `NotFound`, …);
  the central handler turns them into `{"detail": "..."}` with the right status.
  Unhandled exceptions are logged with the request id and return a generic 500.
* Integrations never import app settings — `main.configure_integrations()`
  wires them from `Settings` at startup.
* Routers never build email bodies — they call `app.notifications.send_*`.

## Data model

Tables (see `docs/04_data_model.md` for every column, index and CHECK):

| Table | What |
|---|---|
| `businesses` | the company: identity, address, how it trades, `verification_status` (`draft` → `pending_verification` → `verified` / `rejected`) |
| `users` | people who log in; `business_id` (one business each), `role` (`owner` now), `account_status`, `full_name`, `position`, `phone`, consent, `display_currency` |
| `email_codes` | hashed 6-digit codes keyed by email (`signup` now; `reset_password` / `invite` later) |
| `business_documents` | KYB files of a business (`doc_type`, `storage_key`, review state) |
| `products` | listings of a business (`currency`, `price_usd` + `price_usd_as_of`, soft delete `deleted_at`) |
| `exchange_rates` | daily USD-based rates (`1 USD = rate × quote`), one row per currency per day |
| `contact_reveals` | business-to-business introductions (unique per buyer business + product) |
| `admin_actions` | append-only audit (`business.verify|reject|update`, `doc.approve|reject`) |

Integrity lives in the database: partial UNIQUE indexes on live rows
(legal name, website, phone, one owner per business), CHECKs for status
consistency, enums-as-text values, amounts, `moq <= quantity`, lowercase
email, code attempts, document size and no self-reveal. Services pre-check the
user-facing ones and map a racing `IntegrityError` to the same 409 / 400.
Countries are ISO alpha-2 everywhere (alpha-3 input is converted).

## Key flows

**Signup (one screen)** — `POST /auth/signup/code {email}` checks the work
email (no free-mail / disposable), enforces a 60 s resend cooldown and 5
codes/hour per email (DB-backed) + 20/h per IP, stores an HMAC-SHA256 of a
6-digit code (10 min) and emails it. With `DEBUG=true` the response also
carries `devCode` (never in production). `POST /auth/signup/verify {email,
code}` allows 5 wrong tries, then the code is dead. `POST
/auth/signup/complete {email, fullName, position?, password, acceptTerms}`
needs a verified, unconsumed code (verified ≤ 30 min ago) and in one
transaction creates the business (`draft`) + owner user (consent stamped) and
consumes the code; it sets the session cookie and returns the login shape. An
existing email → 409 "account exists, please log in".

**Login / sessions** — `POST /auth/login` (email + password) sets the
`cor1x_session` cookie (HttpOnly, signed, 24h) — the *only* way to
authenticate a user. It carries `users.session_version`; `POST
/auth/change-password` (current password required), `POST /auth/logout-all`
and account deletion bump the version and revoke every outstanding cookie
(the password-change response re-issues one for this browser). `POST
/auth/logout` clears this browser's cookie. Disabled accounts can't log in.

**Verification** — Passport saves never change status. `POST
/me/submit-verification` moves the user's business from `draft`/`rejected` to
`pending_verification` once the seven mandatory fields are filled (owner's
full name, position, phone; business legal name, industry, operating
countries, trade position). Admins approve from `pending_verification` or
`rejected` and reject from `pending_verification` or `verified` (revoke),
always with a reason. Every admin decision/edit is written to `admin_actions`
(`target_type = business | document`); emails go out in the background.

**Market** — a listing is visible when the product isn't deleted and its
business is `verified` and not deleted. Contact reveal needs both businesses
verified, never the own business, is idempotent per (buyer business,
product) and limited to 20 new reveals per buyer business per hour.

**Exchange rates (multi-currency prices)** — a listing's price is never
changed: it stays `price_per_unit` + `currency` (one of
`FX_SUPPORTED_CURRENCIES`, default `INR,AED,USD`; others → 400). For
comparing and filtering, every listing also carries `price_usd` (2 dp) and
`price_usd_as_of`, computed with the latest stored rate on create and
recomputed for all non-deleted listings after each refresh (one `UPDATE` per
currency). Rates live in `exchange_rates`; **requests only read that table**.

* Fetching — `app/integrations/fx` (same pattern as email/SMS: ABC +
  providers, wired by `main.configure_integrations`, never imports
  settings). `FX_PROVIDERS` is a fallback chain tried per currency:
  Frankfurter v2 (`api.frankfurter.dev/v2/rates?base=USD&quotes=INR,AED`) →
  fawazahmed0 currency-api (jsDelivr, Cloudflare Pages mirror). HTTP calls
  have a timeout and retry with backoff (`_retry.py`). AED falls back to its
  peg (3.6725, source `pegged`). `static` serves fixed rates (tests/offline).
* Sanity bounds — a rate ≤ 0 or one that moved more than
  `FX_MAX_CHANGE_PCT` (20%) vs the last stored rate is logged and dropped;
  the last rate is kept. A currency no provider returns also keeps its last
  rate. Upsert key: `(base, quote, as_of)`.
* Scheduling — with `FX_ENABLED=true` the API lifespan starts one asyncio
  task: it refreshes on start when today's rates are missing (or only the
  0020 `manual` bootstrap exists), then every `FX_REFRESH_HOURS` (24); a
  failed run retries after 15 min; it is cancelled on shutdown. **It runs
  per process** — fine for the single uvicorn process on Railway; with
  several workers set `FX_ENABLED=false` and run
  `python scripts/refresh_rates.py` from cron / a Railway cron service
  (it prints the stored rates; exit 1 when nothing was stored).
* API — `GET /public/fx/rates` → `{base: "USD", asOf, rates: {USD, INR,
  AED}, source}`. Public cards/detail include `priceUsd`, `priceUsdAsOf`.
  `GET /public/products?minPrice=&maxPrice=&priceCurrency=INR|AED|USD`
  converts the bounds to USD (min floored / max ceiled to the cent) and
  filters on `price_usd`; without `priceCurrency` the bounds are USD; 503 if
  the needed rate isn't stored yet. Facets `priceMin`/`priceMax` are USD
  (`priceCurrency: "USD"`, `fxAsOf`).
* Display currency — `users.display_currency` (IN → INR, AE → AED, else
  USD at signup; `ck_users_display_currency`). `GET /me` returns
  `displayCurrency`; `PATCH /me {"displayCurrency": "AED"}` changes it.

**Files** — uploads are sniffed by magic bytes (PDF/JPEG/PNG/WEBP); the stored
extension comes from the detected type, never the filename. Product photos are
public at `GET /uploads/products/<hex>.<ext>` (correct Content-Type,
`nosniff`, `inline`). KYB documents are private: any user of the business
downloads `/me/verification-docs/{id}/file`, admins `/admin/docs/{id}/file`.

**Rate limits** (production budgets; ×`RATE_LIMIT_DEBUG_MULTIPLIER` when
`DEBUG=true`) — login 10/15min per email + 50/15min per IP, signup code
60 s cooldown + 5/h per email (DB) + 20/h per IP, code verify 30/15min per IP,
signup complete 20/h per IP, admin login 10/15min per IP, contact reveal 20
new reveals/h per buyer business (DB-backed). Exceeding returns 429 with
`Retry-After`. The memory backend is per process — add a Redis backend before
running several workers.

**CSRF** — every POST/PUT/PATCH/DELETE whose `Origin` (or `Referer`) is not
one of `CORS_ORIGINS` / `FRONTEND_BASE_URL` gets 403 (`app/core/csrf.py`);
localhost origins are trusted only when `DEBUG=true`. Requests with neither
header (curl, server-to-server) pass. In production make sure `CORS_ORIGINS`
lists the real frontend URL, or the frontend's own requests will be refused.

**Client IP** — per-IP limits read the client from `X-Forwarded-For`
*right to left*, skipping `RATE_LIMIT_TRUSTED_PROXIES` hops (the proxies we
run). The left side of that header is client-controlled, so it is never
trusted. Set it to 1 behind Railway's edge, 2 if requests also pass through
the frontend's `/api` proxy; 0 (default) ignores the header.

## Local development (SQLite)

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env                       # defaults work as-is for dev

# Revisions 0010–0017 are Postgres-only, so build SQLite from the models and
# stamp it at head (later migrations then apply normally):
.venv/bin/python scripts/init_local_db.py           # --force to recreate
.venv/bin/python scripts/seed_test_users.py         # optional
.venv/bin/python scripts/seed_demo.py               # optional catalog data
.venv/bin/python scripts/refresh_rates.py           # optional: today's FX rates now

.venv/bin/uvicorn app.main:app --reload --port 8000
# or from the repo root: backend/.venv/bin/python -m uvicorn --app-dir backend app.main:app --reload
```

Emails land in `backend/outbox/*.eml` (console provider). With `DEBUG=true`
the signup-code response also includes `devCode`. API docs:
http://localhost:8000/docs. Set `ADMIN_PASSWORD_HASH` to use the admin console.

## Postgres (production / Railway)

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/cor1x alembic upgrade head
```

Railway builds with Railpack (`railpack.json`: `alembic upgrade head && uvicorn
...`) and health-checks `GET /health` (`{"status":"ok"}`, 503 when the DB is
unreachable). Production checklist: `DEBUG=false`, `SESSION_SECRET`,
`ADMIN_SESSION_SECRET`, `ADMIN_PASSWORD_HASH`, `CROSS_SITE_COOKIES=true` when
frontend and API are on different sites, `EMAIL_PROVIDER=resend|brevo` +
`EMAIL_API_KEY`, `STORAGE_DIR` on a mounted volume, `LOOKUPS_STUB=false`,
`FX_ENABLED=true` (single process) or a cron running `scripts/refresh_rates.py`.

## Migrations

* Never edit 0001–0018 (production is past them).
* `0019_business_entity` moves the data into the business-centric model
  (docs/04_data_model.md → "Migration from the current schema"). It is
  **one-way** (downgrade raises) — take a backup first. It deletes accounts
  that never set a password, cleans data that would violate the new CHECKs
  (logged as `0019: fixed …`) and only moves data when run online (`--sql`
  renders the DDL only).
* `0020_exchange_rates` adds `exchange_rates`, `products.price_usd(_as_of)`
  and `users.display_currency`; it inserts bootstrap rates (1 USD = 95 INR
  `manual`, 3.6725 AED `pegged`, dated the migration day) so existing
  listings get `price_usd` immediately, and backfills `display_currency`
  from the business country. Real rates replace the bootstrap on the first
  fetch. Reversible (downgrade drops it all).
* New migrations must run on both dialects: use `op.batch_alter_table` for
  ALTERs (env.py sets `render_as_batch` on SQLite) and keep data backfills in
  Python, not dialect-specific SQL.
* Check Postgres SQL renders offline:
  `DATABASE_URL=postgresql://u:p@localhost/x alembic upgrade 0018_hardening:head --sql`

```bash
alembic revision -m "describe change"
alembic upgrade head
```

## Tests

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Tests run the real app through `httpx.ASGITransport` against a throwaway SQLite
DB, the console email/SMS providers, the static FX provider (no network,
no background refresh) and a temp storage dir (see
`tests/conftest.py`). They never touch `backend/cor1x.db`.

## Endpoints

| Area | Endpoints |
|------|-----------|
| Health | `GET /health` |
| Auth | `POST /auth/signup/code`, `POST /auth/signup/verify`, `POST /auth/signup/complete`, `POST /auth/login`, `POST /auth/change-password`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/session` |
| Account | `GET /me`, `PATCH /me` (`displayCurrency`), `DELETE /me`, `POST /me/submit-verification`, `GET /onboarding/status`, `POST /onboarding/company`, `POST /onboarding/contact`, `POST /onboarding/business` |
| KYB docs | `GET/POST /me/verification-docs`, `GET /me/verification-docs/{id}/file`, `DELETE /me/verification-docs/{id}` |
| Catalog | `GET/POST /products`, `DELETE /products/{id}`, `POST /products/upload-photo`, `POST /products/{id}/contact-reveal`, `GET /public/products`, `GET /public/products/{id}`, `GET /public/catalog/facets`, `GET /public/fx/rates`, `GET /uploads/products/{file}` |
| Lookups | `GET /pincode/{pincode}`, `GET /ifsc/{code}` |
| Admin | `POST /admin/login`, `POST /admin/logout`, `GET /admin/me`, `GET /admin/dashboard/{stats,timeline,stuck}`, `GET /admin/verify/queue`, `GET /admin/users`, `GET/PATCH /admin/users/{id}`, `POST /admin/users/{id}/{verify,reject}` (act on the user's business), `GET /admin/docs/pending`, `GET /admin/docs/{id}/file`, `POST /admin/docs/{id}/{approve,reject}` |
