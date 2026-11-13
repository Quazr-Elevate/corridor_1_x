# Architecture and patterns

How the backend is put together, with the shapes the existing code actually uses.
Copy these rather than inventing new ones. Paths are relative to `backend/`.

## Contents

- [Request path](#request-path)
- [Where things live](#where-things-live)
- [A module's five files](#a-modules-five-files)
- [Pattern: trader route](#pattern-trader-route)
- [Pattern: service function](#pattern-service-function)
- [Pattern: schemas](#pattern-schemas)
- [Pattern: admin route with audit](#pattern-admin-route-with-audit)
- [Pattern: admin permission](#pattern-admin-permission)
- [Pattern: rate limit](#pattern-rate-limit)
- [Pattern: migration](#pattern-migration)
- [Transactions](#transactions)
- [Integrations](#integrations)
- [Configuration and startup](#configuration-and-startup)
- [New modules in later milestones](#new-modules-in-later-milestones)

## Request path

```
browser ─ lib/api.ts (credentials: include) ─ Next.js /api rewrite ─┐
                                                                    ▼
RequestContextMiddleware   request id; actor=user:<id>/admin:<id> in the access log
SecurityHeadersMiddleware  HSTS on HTTPS, nosniff, Referrer-Policy, frame-ancestors, no-store
CORSMiddleware             listed origins only; localhost regex only when DEBUG
CSRFOriginMiddleware       Origin check on state-changing requests
router  →  service  →  models  →  Postgres (SQLite in tests)
```

The middleware order in `app/main.py` is deliberate: CSRF is innermost, so CORS
still decorates its 403. Don't reorder it without a reason written in the PR.

Errors raised anywhere below the router go through
`core/errors.register_exception_handlers` and come out as `{"detail": "..."}`.

## Where things live

| Path | Holds |
|---|---|
| `app/main.py` | `create_app()`: config checks, `configure_integrations()`, middleware, router list |
| `app/core/` | `config` settings · `security` sessions, cookies, `parse_uuid` · `crypto` AES-256-GCM for KYB values · `csrf` · `headers` · `errors` · `logging` · `db` engine and session · `time` |
| `app/models/` | One SQLAlchemy table per file; `base.py` holds `Base` and `UTCDateTime` |
| `app/modules/<area>/` | One feature area: `router`, `service`, `schemas`, sometimes `deps`, `queries`, `rules` |
| `app/shared/` | Cross-module: `schemas.CamelModel`, `text()`; `files.file_response`; `countries`; `normalize` |
| `app/integrations/` | `email`, `sms`, `fx`, `storage`, `lookups` — provider-swappable |
| `app/notifications/templates/` | Outbound email templates |
| `app/ratelimit/` | `RateLimitRule`, `get_limiter()`; in-memory backend now, Redis in Phase B (CX-009) |
| `alembic/versions/` | `0001`–`0024`; `0018` onward portable to SQLite |
| `scripts/` | `init_local_db.py`, `create_admin.py` |
| `tests/` | pytest + httpx; `conftest.py` fixtures; `tests/qa/` journey tests |

Current modules: `accounts`, `admin`, `auth`, `catalog`, `fx`, `health`,
`lookups`, `verification`. Trader cookie `cor1x_session`, admin cookie
`cor1x_admin`; the two never share a session or a dependency.

## A module's five files

| File | Does | Never does |
|---|---|---|
| `router.py` | Declares routes: path, auth dependency, `response_model`, status code; calls one service function | Business `if`s, queries, building responses by hand |
| `service.py` | Business rules, queries, state changes; raises `core/errors` exceptions | Import FastAPI, read cookies, know about HTTP |
| `schemas.py` | Pydantic request and response models on `CamelModel`, constrained field types, `*_to_read()` mappers | Hold logic beyond shape and validation |
| `deps.py` | `Annotated` auth and permission dependencies | Anything else |
| `queries.py` / `rules.py` | Reusable query clauses (`visible_products_clause`) and pure rule functions, when the service gets long | Commit |

Models live in `app/models/`, not in the module, because more than one module
reads most tables.

## Pattern: trader route

```python
# app/modules/catalog/router.py
products_router = APIRouter(prefix="/products", tags=["products"])

@products_router.post("", response_model=ProductRead, response_model_by_alias=True, status_code=201)
async def create_product(payload: ProductCreate, user: CurrentUser, db: DbSession) -> ProductRead:
    return product_to_read(await service.create_product(db, user, payload))

@products_router.delete("/{product_id}", status_code=204, response_class=Response)
async def delete_product(product_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_product(db, user, parse_uuid(product_id))
    return Response(status_code=204)
```

What to notice: one line of work per route; `response_model_by_alias=True` for
camelCase; IDs arrive as `str` and go through `parse_uuid` (a malformed value
becomes `None`, the lookup finds nothing, the service raises `NotFound`);
explicit 201 and 204.

Dependencies, from `app/modules/auth/deps.py`:

| Alias | Meaning |
|---|---|
| `CurrentUser` | Signed-in trader; 401 otherwise |
| `OptionalUser` | Trader or `None`, for public routes that personalise |
| `CurrentSessionId` | The session's id, for sign-out-elsewhere logic |
| `DbSession` | The request's `AsyncSession` |

## Pattern: service function

```python
# app/modules/catalog/service.py
async def list_own_products(db: AsyncSession, user: User) -> list[Product]:
    """The business's listings (not deleted), newest first."""
    ...

async def create_product(db: AsyncSession, user: User, payload: ProductCreate) -> Product:
    """Any signed-in user may list for their business; listings only appear
    in the market once the business is verified (``visible_products_clause``)."""
    ...
    db.add(product)
    await commit_or_conflict(db)
    await db.refresh(product)
    return product
```

Rules: the signature is `(db, principal, payload or ids)`; ownership is part of
the query (`Product.business_id == user.business_id`), not a check afterwards;
the function returns model objects and the router maps them; errors are raised:

```python
raise BadRequest("Enter the number or upload the document.")
raise Conflict("A published listing cannot move to draft.")
raise NotFound("Listing not found.")
```

`commit_or_conflict(db)` (in `modules/accounts/uniqueness.py`) commits and turns
a unique-constraint violation into a `Conflict` with a human message. Use it
wherever a write can collide with a unique index.

## Pattern: schemas

```python
# app/shared/schemas.py
class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

# app/modules/catalog/schemas.py: constrained types once, reused everywhere
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]
ProductName = text(200, 2)          # text(max_length, min_length) from shared/schemas
Unit = Literal["MT", "kg", "quintal"]

class ProductCreate(CamelModel):
    name: ProductName
    category: Category
    unit: Unit = "MT"
    price_per_unit: Amount | None = None

def product_to_read(p: Product) -> ProductRead:
    return ProductRead(id=str(p.id), name=p.name, ...)
```

Every string has a max length and every number has bounds, through these types.
Enumerations are `Literal`, matching a database `CheckConstraint`. Responses are
built by a mapper, never by returning the ORM object.

*Proposed, not yet approved (see `decisions.md`)*: a `RequestModel` base with
`extra="forbid"` for request bodies. Until it's approved, request models stay on
`CamelModel`.

## Pattern: admin route with audit

```python
# app/modules/admin/docs.py
@router.post("/docs/{doc_id}/reveal", response_model=RevealedValue, response_model_by_alias=True)
async def reveal_doc_value(doc_id: str, admin: CanViewSensitive, db: DbSession) -> RevealedValue:
    """Full number of a KYB entry (audited)."""
    await get_limiter().check(ADMIN_REVEAL, str(admin.id))
    doc = await docs_service.get_doc(db, parse_uuid(doc_id))
    ...
    service.record_action(
        db, admin=admin, action="kyb.value_viewed", target_type="business_document",
        target_id=doc.id, details={"business_id": str(doc.business_id)},
    )
    await db.commit()
```

The admin principal comes from a permission alias, never `SignedInAdmin` when a
specific permission applies. Rate limit first. The audit row and the change
commit together. Action names are `entity.verb`, matching the existing rows:
`business.verify`, `business.reject`, `kyb_type.create`, `user.unlock`. Views of
sensitive data use the past participle: `kyb.value_viewed`, `kyb.file_viewed`.
A new listing review writes `listing.approve` and `listing.reject`.

## Pattern: admin permission

```python
# app/modules/admin/permissions.py: deny by default
class Perm(str, enum.Enum):
    kyb_review = "kyb.review"
    listings_review = "listings.review"        # a new permission is one member…

REVIEWER = frozenset({..., Perm.listings_review})   # …plus the roles that hold it

# app/modules/admin/deps.py: …plus one alias
CanReviewListings = Annotated[AdminPrincipal, Depends(require(Perm.listings_review))]
```

The route-matrix test in `tests/test_admin_accounts.py` fails if any `/admin`
route lacks a permission. A new role is a row in `ROLE_PERMISSIONS`. The plan
needs trade desk, quality, finance, logistics and legal roles from M3 (CX-094);
add each when the first route that needs it lands.

## Pattern: rate limit

```python
ADMIN_REVEAL = RateLimitRule("admin.kyb_reveal:admin", limit=200, window_sec=60 * 60)
...
await get_limiter().check(ADMIN_REVEAL, str(admin.id))
```

Rule names are `area.action:scope`, and the key is the principal's id (or the
client IP for anonymous routes). Limit anything that reveals, uploads, signs in,
sends email or SMS, calls a third party, or costs credits. The limiter raises
`RateLimitExceeded`, which becomes a 429 with `Retry-After`.

## Pattern: migration

```python
"""countries table; FKs from businesses.country and kyb_document_types.country

Revision ID: 0023_countries
Revises: 0022_reject_items
Create Date: 2026-10-31

Implements docs/04_data_model.md → "Countries (0023)":

* new table ``countries`` (...);
* seeded with India and the UAE, plus every code already used ... so the new
  foreign keys never fail on existing data;

Portable (Postgres + SQLite batch ops). Reversible.
"""
revision: str = "0023_countries"
down_revision: Union[str, None] = "0022_reject_items"
```

The revision ID equals the file name. The docstring says what changes, points at
the `04_data_model.md` section, explains how existing rows are handled, and ends
with portability and reversibility. Use `op.batch_alter_table` so SQLite can run
it. Backfill in the same migration. See `testing.md` for the migration test.

## Transactions

- A trader service commits its own unit of work, usually through
  `commit_or_conflict`.
- An admin route that writes an audit row after the service call commits in the
  router, so the change and its audit land in one transaction. The service
  changes objects on the session and leaves the commit to the router.
- Follow whichever the neighbouring code does, and never commit twice for one
  logical action. Anything that moves money (M5) is one transaction, or a
  documented saga with compensation. Never "commit and hope".
- Files are written or removed **after** the commit succeeds (see account
  deletion), so a rolled-back transaction never leaves an orphan or deletes a
  live file.

## Integrations

`email`, `sms`, `fx`, `storage`, `lookups` each expose an interface and get a
config object in `main.configure_integrations()`. Callers use the interface and
never know the provider. Tests swap them through `app.dependency_overrides` or
the stub settings (`LOOKUPS_STUB`, the console email outbox). Every outbound call
needs a timeout, a bounded retry, and validation of what comes back: treat
third-party responses as untrusted input (OWASP API10).

## Configuration and startup

Settings come from environment variables in `core/config.py`. `create_app()`
refuses to start with `DEBUG=false` on development defaults
(`insecure_defaults()`) and warns when KYB encryption runs on the development
key. A new secret or flag goes into `Settings` with a safe default, into
`.env.example`, and, if it matters in production, into `insecure_defaults()`.

## New modules in later milestones

Each one is the same five-file shape, registered in the router tuple in
`create_app()`, with its tables documented in `04_data_model.md`.

| Milestone | New |
|---|---|
| M1 | `category_templates`, `product_specs`, listing `status`; `admin/products.py` (the review queue, under `/admin/products/...`) |
| M2 | `modules/masking` + `identity_vault` schema; `modules/credits`; `shared/leakfilter.py` |
| M3 | `models/deal.py` + `modules/deals` (the state machine); `modules/rfq`; `modules/quotes` |
| M4 | `modules/chat`, `modules/negotiation`, `modules/samples`, `modules/contracts` |
| M5 | `modules/payments`, `modules/ledger`, `modules/inspection`, `modules/logistics`, `modules/execution` |
| M6 | `modules/claims` |
| M7 | storage, rate limiting, auth (TOTP) and infrastructure, no new trade module |
