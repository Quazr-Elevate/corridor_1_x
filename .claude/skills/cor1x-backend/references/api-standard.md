# REST API standard

Every endpoint in every milestone follows this. Each rule is marked:

- **Current**: how the code works today. Follow it.
- **Proposed**: agreed direction, waiting for approval in `decisions.md`. Don't
  implement it until it's approved or the user asks for it directly.
- **From Mx**: applies once that milestone starts.

## Contents

- [Resources and paths](#resources-and-paths)
- [Methods](#methods)
- [State changes are actions](#state-changes-are-actions)
- [Requests](#requests)
- [Responses](#responses)
- [Collections](#collections)
- [Errors](#errors)
- [Status codes](#status-codes)
- [Versioning](#versioning)
- [Concurrency](#concurrency)
- [Idempotency](#idempotency)
- [Money, dates and IDs](#money-dates-and-ids)
- [Designing a new endpoint](#designing-a-new-endpoint)

## Resources and paths

**Current.** Plural nouns, lowercase, hyphens between words.

| Audience | Prefix | Example |
|---|---|---|
| The signed-in trader's own data | `/me/...` | `GET /me/verification-docs` |
| Trader-owned collections | `/<resource>` | `POST /products` |
| Anonymous | `/public/...` | `GET /public/products?category=Rice` |
| Corridor staff | `/admin/...` | `POST /admin/docs/{docId}/approve` |
| Served files | `/uploads/...` | `GET /uploads/products/{file}` |

Nest at most one level (`/products/{id}/certificates`). Deeper relations get
their own top-level resource with a filter. Keep the existing name `products`
for listings: renaming a resource costs every client and buys nothing.

## Methods

**Current.**

| Method | Use | Never |
|---|---|---|
| `GET` | Read | Change state, including counters and "mark as seen" |
| `POST` | Create, or perform an action (below) | Read |
| `PATCH` | Partial update of plain fields | Change `status`, owner, or anything with a rule attached |
| `PUT` | Replace a whole sub-document (the business profile does this) | Partial updates |
| `DELETE` | Remove (soft delete where the table has `deleted_at`) | Bulk delete without a filter |

## State changes are actions

**Current pattern, mandatory from M1.** A status change is a `POST` to an action
sub-resource, never a `PATCH {"status": ...}`:

```
POST /products/{id}/submit            draft → under_review
POST /admin/products/{id}/approve     under_review → published
POST /admin/products/{id}/reject      under_review → rejected     body: {"reason": "..."}
POST /admin/docs/{docId}/approve      (exists today)
POST /me/submit-verification          (exists today)
```

Why: an action has its own permission, its own body (a reason, an amount), its
own rate limit and its own audit row, and it calls the entity's single transition
function. A wrong-state request is **409** with a message that names both states.

## Requests

- **Current.** camelCase JSON; both casings accepted (`populate_by_name=True`).
- **Current.** Every string has a max length and every number has bounds, through
  the shared types (`text()`, `Amount`, `Currency`, `Literal` enums).
- **Current.** Query parameters are validated with `Query(..., max_length=, ge=, le=)`.
- **Current.** Path IDs are strings parsed with `parse_uuid`.
- **Current (A-013).** Unknown body fields are **rejected** (422
  `request.unknown_field`). Every request schema, nested ones included,
  inherits `RequestModel` (`app/shared/schemas.py`, `extra="forbid"`);
  `tests/test_api_contract.py` walks the routes and fails on a loose one.
- **Always.** The client never sends anything the server owns: `id`,
  `businessId`, `status`, `createdAt`, internal prices or margins, approval
  fields. If a schema declares such a field for input, that's a bug.

## Responses

**Current.** Always an explicit `response_model` with
`response_model_by_alias=True`, built by a `*_to_read()` mapper. Never return an
ORM object, because a column added later would leak the day it's added.

Shape rules:
- One resource → the object itself, no wrapper.
- A collection → the envelope below.
- An action → the resource in its new state (so the client doesn't need a second GET).
- A delete → 204, no body.
- Fields the caller may not see are **absent**, not `null`. A masked value is a
  different field (`valueLast4`), never the real field with stars in it.

## Collections

**Current on `/public/products` and `/admin/users`; required for every new list:**

```json
{ "items": [ ... ], "total": 137 }
```

with `limit` (bounded: default 24 or 50, maximum 60 or 200) and `offset` query
parameters, and a stable sort: newest first by `created_at`, then `id` as the
tiebreaker so pages never repeat or skip rows.

**From M1:** the four lists that return bare arrays today (`GET /products`,
`GET /me/verification-docs`, `GET /admin/admins`, `GET /admin/docs/pending`) move
to the envelope, alongside the listing work.

**From M4:** high-volume feeds (chat messages, the ledger) use cursor pagination
(`?after=<opaque cursor>`), because offsets drift while rows are being added.

Filters are named query parameters (`?category=Rice&minPrice=40`), never a
query language. Free-text search is `q`.

## Errors

**Current (A-012):** services raise `BadRequest`, `Unauthorized`, `Forbidden`,
`NotFound`, `Conflict` from `core/errors.py`. Each class carries a stable
`code` (`auth.required`, `resource.not_found`, …) and a service can pass its
own with `code=`. Validation errors, framework errors (unknown path, wrong
method), the rate limiter and the CSRF check all return the same shape.

**One shape for every error** (`detail` is always a string; clients branch on
`code`):

```json
{
  "detail": "Price range is invalid.",
  "code": "validation.failed",
  "fields": [{ "field": "maxPrice", "message": "Must be greater than or equal to minPrice." }]
}
```

- `detail`: always a sentence a user can act on (see `code-style.md` for the voice).
- `code`: stable, `area.reason`, for clients to branch on: `listing.invalid_transition`,
  `auth.locked`, `credits.insufficient`, `rate_limited`.
- `fields`: only on validation errors, using the request's camelCase names.

Never put a stack trace, SQL, file path, other business's data, or whether an
email is registered into an error.

## Status codes

| Code | When |
|---|---|
| 200 | Read, update, action |
| 201 | Created; return the new resource |
| 204 | Deleted, or an action with nothing to return |
| 400 | A business rule refused the input |
| 401 | Not signed in, or the session expired |
| 403 | Signed in but not allowed: wrong role, or the business isn't verified (the KYB gate) |
| **404** | Not found **or not yours**. Never 403 for another business's resource |
| 409 | Wrong state for this action, or a duplicate |
| 412 | Stale edit (from M1, see Concurrency) |
| 413 / 415 | Upload too large / wrong type |
| 422 | The body or query failed validation |
| 429 | Rate limited, with `Retry-After` |
| 500 | Our bug. Generic message, details only in the logs |
| 502 / 503 | A third party failed (`UpstreamError`) / we are degraded |

## Versioning

**Current (A-011).** Every route is under `/v1/...` except `/health`: one prefix
in `create_app()`. The frontend adds the version in `lib/apiBase.ts`, so the
configured base names the host only. Test paths are relative to `/v1`
(`conftest.ROOT_URL` reaches outside it). A breaking change means `/v2` for
that resource, and an additive change (a new optional field, a new endpoint)
never needs a version.

**API docs (A-014).** `/docs`, `/redoc` and `/openapi.json` exist only when
`DEBUG=true`. `scripts/export_openapi.py` writes the schema; CI keeps it as an
artifact.

**Additive by default, always:** add fields, never rename or remove them without
a version; new request fields are optional or have defaults.

## Concurrency

**From M1** for anything several people edit (listings under review, term
sheets, contracts, admin-edited business profiles): the resource carries an
integer `version`; a `PATCH` or action sends the version it read; a mismatch is
**412** with "This was changed by someone else. Reload and try again." The
database update is `WHERE id = :id AND version = :version`, not a read-then-check.

## Idempotency

**From M2** for anything that costs credits or creates a billable thing, and
**from M5** for anything that moves money: the client sends an
`Idempotency-Key` header (a UUID). The server stores the key with the response
for 24 h, and a repeat with the same key returns the stored response without
doing the work twice. Webhooks are idempotent on the provider's event id.

## Money, dates and IDs

- **IDs**: UUIDs, as strings in JSON.
- **Dates and times**: ISO 8601 UTC, `2026-11-16T09:30:00Z`; plain dates `2026-11-16`.
- **Money, current**: listing prices are decimals with a separate `currency`.
- **Money, from M5**: `{"amount": 64800000, "currency": "USD"}`. An integer in
  minor units, never a float, never a formatted string. Display formatting is
  the client's job.
- **Percentages**: decimals in a named field (`marginPct: "4.90"`), never a bare
  number whose unit you have to guess.

## Designing a new endpoint

Write this table in the milestone's design review for each endpoint before any
code. The design review template has it ready.

| Field | Example |
|---|---|
| Method + path | `POST /admin/products/{productId}/reject` |
| Purpose | Reviewer rejects a listing with a reason the seller will see |
| Auth | `CanReviewListings` |
| Request | `{"reason": text(500, 10)}` |
| Response | `200` `ListingRow` in state `rejected` |
| Errors | 404 unknown or deleted · 409 not under review · 422 reason missing or short |
| Rate limit | none (staff action, audited) |
| Audit | `listing.reject` with the reason |
| Idempotent? | Yes by state: a second reject gets 409 |
| Tests | rule · happy path · 409 · stranger 404 · reviewer without permission 403 |
