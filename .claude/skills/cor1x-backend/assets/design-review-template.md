# Mx design review — <milestone name>

**Status:** Draft · Approved on <date> by <who>
**Sprints:** Sx–Sy · **Phase:** A / B · **Plan sections:** …
**Rows:** CX-… (every row in the milestone, from the tracker)

> Present this to the user in plain language: tables first, then the decisions,
> each with a recommendation. Nothing in a section marked *Open* is built until
> it's answered.

## 1. What this milestone delivers

Two or three sentences a non-engineer can follow: what a trader or staff member
can do at the end that they can't do now.

**Exit gate** (copied from the Roadmap sheet; each line must be provable):
- …

## 2. Data model

For each new or changed table:

| Table | Change | Columns (type, null, default) | Constraints and indexes | Sensitive? |
|---|---|---|---|---|
| `products` | add | `status varchar(20) not null default 'draft'` | `ck_products_status`; market partial index gains `status = 'published'` | No |

**Migrations:** `00NN_name`: what it does to existing rows (the backfill),
portable to SQLite, reversible? Which `04_data_model.md` sections change.

**State machine** for every entity with a status:

| From | Action | To | Who | Guard |
|---|---|---|---|---|
| draft | submit | under_review | owning seller | required fields present |

## 3. API

One table per endpoint (fields from `references/api-standard.md`):

| | |
|---|---|
| **Method + path** | `POST /products/{productId}/submit` |
| **Purpose** | … |
| **Auth** | `CurrentUser` (owner) / `Can…` |
| **Request** | `{ "field": type and bounds }`, or none |
| **Response** | `200 ProductRead` (state after) |
| **Errors** | 404 not found or not yours · 409 wrong state · 422 … |
| **Rate limit** | rule name and limit, or "none: why" |
| **Audit** | action name, or none |
| **Idempotency** | by state / Idempotency-Key / n.a. |

Show one full example request and response body for the main endpoint of each
area, in camelCase JSON.

**Changed existing endpoints:** what changes in the response shape and which
frontend calls must change with it.

## 4. Business rules

Numbered rules in plain language, each one testable. Where the plan leaves a
value open (a window, a percentage, a limit), give the default you'll use and
make it configuration.

## 5. Security

1. New data stored, its sensitivity, and how it's protected (encrypted, masked, vault)
2. Who can call each endpoint, and how ownership is enforced in the query
3. What can be abused at volume, and the limit or cost that stops it
4. What leaves the system: emails, files, third-party calls, and what each contains
5. What's audited
6. Failure mode if the least reliable dependency is down
7. Controls in `docs/05_security_review.md` whose status changes

## 6. Tests

| Rule or endpoint | Rule test | Happy path | Refusal | Access (404 / 403 / 401) | Migration |
|---|---|---|---|---|---|

## 7. Frontend impact

Which pages and API-client calls change, so the frontend work can be planned
alongside, not discovered.

## 8. Out of scope

What someone might expect in this milestone that isn't in it, and where it lives instead.

## 9. Decisions needed

| # | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|

## 10. Risks

What could make this milestone slip or go wrong, and what we'll do about each.
