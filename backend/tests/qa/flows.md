# QA — Business flow inventory

Source of truth for the test IDs in `tests/qa/test_*.py`.
Covers every behaviour introduced on branch `work/pegan-2026-10-21`.
Each flow has a `FLOW-NNN` id; each test case references its flow.

---

## FLOW-100 — Signup country at Step 3

`POST /auth/signup/complete` adds a mandatory `country` field (ISO alpha-2).
On success:
- `business.country` set to the submitted value
- `business.operating_countries` auto-seeded with `[country]`
- A session cookie is issued

Negative:
- Missing country → 422 "Field required"
- Invalid code (`"XX"`, `"I"`) → 422 "Unknown country code"
- Lowercase (`"in"`) or alpha-3 (`"IND"`) normalized to alpha-2 → accepted

Tests: `tests/qa/test_signup_country.py` (QA-100.*)

---

## FLOW-200 — Admin manages country doc catalog (CRUD)

Admin screen: `/admin/doc-requirements`. Routes:
- `GET /admin/doc-requirements?country=&includeInactive=`
- `POST /admin/doc-requirements` — create
- `PATCH /admin/doc-requirements/{id}` — edit mutable fields (`display_name`,
  `description`, `help_url`, `is_mandatory`, `is_active`). `country_code`
  and `slug` are intentionally immutable (not in the schema).

Negative:
- Non-admin → 401
- Slug fails regex (`^[a-z0-9][a-z0-9_-]{0,39}$`) → 422
- Unknown country → 422
- `help_url` with scheme other than http(s) → 422 (`javascript:`, `data:`, `ftp:`)
- Duplicate active (country, slug) → 409
- Empty display_name → 422 min_length

Tests: `tests/qa/test_doc_requirements.py` (QA-200.*)

---

## FLOW-300 — Trader sees required slots for their country

- `GET /me/verification-docs/requirements` → grouped `required` / `optional`
  slots for the business's country, plus `custom_uploads` list.
- Each slot carries `displayName`, `slug`, `isMandatory`, `helpUrl`, `upload`.
- Changing admin catalog propagates on next request (no cache).

Negative:
- Unauthenticated → 401

Tests: `tests/qa/test_trader_requirements.py` (QA-300.*)

---

## FLOW-400 — Trader uploads to a mandatory slot

`POST /me/verification-docs` with `required_doc_type_id` form field.

- Target slot must be active and belong to the business's country.
- Replace semantics: a second upload for the same (business, slot) deletes
  the previous file + row, so each slot holds at most one upload.
- Doc returned carries `requirementSlug` + `requirementDisplayName`.

Negative:
- Cross-country slot id → 400 "different country"
- Non-existent / inactive slot id → 400
- Upload wrong MIME → 415
- Oversize (>10 MB) → 413

Tests: `tests/qa/test_trader_upload.py` (QA-400.*)

---

## FLOW-500 — Submit for verification gated on fields + mandatory docs

`POST /me/submit-verification`:
- All 7 profile mandatory fields must be filled.
- Every active mandatory requirement for the business's country must
  have a non-rejected upload.
- `verification_state.missing` contains `doc:<slug>` tokens for each
  unfilled mandatory doc.
- `verification_state.mandatory_total` = 7 + mandatory doc count.

Negative:
- Submit before docs → 400 with the missing slot display name in the message.
- Submit before all 7 fields → 400 with field keys.
- Already verified business → 400 "nothing to submit".

Tests: `tests/qa/test_submit_gate.py` (QA-500.*)

---

## FLOW-600 — Admin single-review (business cert + 7 fields)

Replaces the pre-branch separate "KYB queue" + "Docs queue" flow.

- `GET /admin/verify/queue` returns businesses in `pending_verification`
  with their uploaded docs (each with slug + display name).
- `POST /admin/users/{user_id}/verify` approves business AND cascades
  every pending/rejected mandatory cert doc to `approved`.
- `POST /admin/users/{user_id}/reject` with `reason` + `failed_items[]`
  (subset of `MANDATORY_FIELDS` keys plus `doc:<slug>` tokens) sets
  business to `rejected`, writes `verification_rejected_items`, and
  cascades each `doc:*` key to the matching upload being flipped to
  `rejected` with the same reason.
- Custom (non-slot) uploads are NOT touched by business approve/reject.

Negative:
- Non-admin → 401
- Approve business with missing mandatory fields → 400
- Reject already-verified business → 200 (revoke flow); reject already
  rejected → 409
- Reject with unknown field keys silently drops them (not an error — the
  textual reason carries the full context)

Tests: `tests/qa/test_single_review.py` (QA-600.*)

---

## FLOW-700 — Trader-side rejection view

`GET /me` after admin reject returns `verification`:
- `status = "rejected"`
- `rejectedReason` = the admin text
- `rejectedItems` = exact keys the admin ticked
- `rejectedItemLabels` = `{doc:<slug> → admin display name}` (field keys
  omitted — the frontend has them locally)
- `missing` includes `doc:<slug>` entries for the rejected docs (so the
  resubmit flow still gates on them being replaced).

Tests: `tests/qa/test_trader_reject_state.py` (QA-700.*)

---

## FLOW-800 — Verified business edit → auto-unverify

If a user with `verification_status == verified` edits ANY of the 7
mandatory profile field values, the backend flips the status back to
`pending_verification` and clears `verified_at` + `verification_rejected_*`.

Non-mandatory field edits (website, intro, etc.) on a verified business
leave the status alone.

Tests: `tests/qa/test_auto_unverify.py` (QA-800.*)

---

## FLOW-900 — Admin doc view (per-doc approve/reject still works)

Side-flow — the "Other certificate" tab in the Docs lane. Per-doc approve
and reject against custom (non-slot) uploads. Pre-branch behaviour,
preserved.

Not covered in the new suite — existing `tests/test_docs.py` + `test_admin.py`
exercise these endpoints.

---

## Role matrix

| Capability | Anonymous | Trader | Admin |
|---|---|---|---|
| Signup Step 3 country | — | ✓ (one-time) | — |
| Upload mandatory doc | — | ✓ | — |
| Submit for verification | — | ✓ | — |
| Doc catalog CRUD | — | 401 | ✓ |
| Verify / reject business | — | 401 | ✓ |
| Business cert single-review | — | 401 | ✓ |
| Trigger auto-unverify (edit mandatory field) | — | ✓ (on own biz) | ✓ (via patch) |

Tests always use isolated per-test accounts via `signup_and_login(...)`
with a UUID-prefixed email so parallel runs don't collide.
