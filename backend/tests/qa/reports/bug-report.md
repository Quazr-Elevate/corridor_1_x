# Bug report — QA pass on `work/pegan-2026-10-21`

Three defects found during this QA pass. Two were fixed in the same
branch; one is deliberately left open with a documenting test (QA-600.4)
so the behavior change is intentional, not accidental.

Severity scale: **Critical** (data loss / security), **High** (blocks a
primary flow), **Medium** (wrong data or wrong UX on a flow with a
workaround), **Low** (edge case or UX nit).

---

## QA-F001 — Admin reject accepts empty `failedItems`

**Severity:** Low
**Status:** **Fixed** — `app/modules/admin/schemas.py::UserRejectIn` now
requires `failed_items` with `min_length=1`; regression covered by
`tests/qa/test_single_review.py::test_reject_with_empty_failed_items_is_rejected`.
**Found via:** QA-600.4

### Repro

1. Create business, fill mandatory, submit for verification.
2. As admin: `POST /admin/users/{uid}/reject` with
   `{"reason": "no items", "failedItems": []}`.
3. **Expected:** `400 {"detail": "pick at least one failed item"}` or similar.
4. **Actual:** `200 OK`; business flips to `rejected` with no items.

### Impact

Trader sees a reject with a reason but no itemised list, so the Docs /
profile UI has no way to flag which fields need fixing. The resubmit
gate (`missing[]`) still works because the mandatory check runs
independently, so the trader can still proceed — hence Low rather than
Medium.

### Root cause

`app/modules/admin/service.reject_business` doesn't enforce
`len(failedItems) >= 1`. The pydantic schema allows `list[str]` with no
`min_length` constraint.

### Fix

Added `min_length=1` to the `failed_items` field on `UserRejectIn`.
Pydantic now returns 422 for an empty list before the handler runs.
Two existing tests (`tests/test_admin.py`, `tests/test_catalog.py`)
that used the loose contract were updated to pass `failedItems: ["legalName"]`.

---

## QA-F002 — `includeInactive` query param ignored

**Severity:** Medium
**Status:** **Fixed** in this branch (`app/modules/admin/doc_requirements.py:33-37`).
**Found via:** QA-200.1 (full lifecycle test)

### Repro (pre-fix)

1. As admin: create a doc requirement, then PATCH `is_active=false`.
2. `GET /admin/doc-requirements?country=IN` — row absent (correct).
3. `GET /admin/doc-requirements?country=IN&includeInactive=true` —
   row still absent (**wrong**; expected to see the row).

### Impact

Admin's Doc-requirements screen couldn't display soft-deactivated rows
even with "show inactive" toggled, so admins had no way to re-enable
them without a DB-side nudge. The deactivate action itself worked, but
was effectively a one-way street from the UI.

### Root cause

The FastAPI handler declared `include_inactive: bool = False` without
an `alias`. The frontend sends `includeInactive` (camelCase); FastAPI
only sees `include_inactive`, so the camelCase query param went to the
default `False`.

### Fix

```python
include_inactive: bool = Query(
    False,
    alias="includeInactive",
    description="Include soft-deactivated rows. Frontend sends camelCase; "
                "the server-side name stays snake_case.",
),
```

See `backend/app/modules/admin/doc_requirements.py:33-37`.

### Regression test

`tests/qa/test_doc_requirements.py::test_full_lifecycle` — passes
after fix.

---

## QA-F003 — Trader doc upload response missing requirement metadata

**Severity:** Medium
**Status:** **Fixed** in this branch (`app/modules/verification/router.py:35-40`).
**Found via:** QA-300.1

### Repro (pre-fix)

1. As admin: seed a mandatory doc requirement for country IN with slug
   `test_cert` and display `Test cert`.
2. As trader (country IN, submitted-ready): `POST /me/verification-docs`
   with form field `required_doc_type_id=<row id>`.
3. **Expected response:** 201 with `requirementSlug="test_cert"` and
   `requirementDisplayName="Test cert"`.
4. **Actual (pre-fix):** 201 with both fields `null`.

### Impact

Frontend's Docs lane renders the cert tile from the upload response's
`requirementDisplayName`. Pre-fix, the tile appeared with the raw
filename only until a page reload refetched `/me/verification-docs`.
Visible UX glitch, no data loss.

### Root cause

`verification.router.upload_doc` called
`doc_to_out(doc)` without a `requirement=` arg, so the serializer had
nothing to fill the `requirementSlug` / `requirementDisplayName` fields
with. The `list_docs_out` path *did* resolve requirements, so the fields
appeared on reload but not on initial upload response.

### Fix

```python
req = None
if doc.required_doc_type_id is not None:
    req = await db.get(BusinessDocumentRequirement, doc.required_doc_type_id)
return doc_to_out(doc, requirement=req)
```

See `backend/app/modules/verification/router.py:35-40`.

### Regression test

`tests/qa/test_trader_docs.py::test_upload_fills_slot_and_populates_display_name`
— passes after fix.

---

## No other defects found

The remaining 39 QA-suite tests passed first time against the branch
without any further app changes. The single-review cascade (approve
and reject paths), the auto-unverify flow, and all country-aware signup
behavior worked as specified.

## Not reproduced

Earlier admin-side UI issue "Business review shows only one mandatory
cert when three were uploaded" and "Cert type name small, filename
large" are **fixed in this branch** (commit `47376a4`) via
`frontend/components/admin/BusinessReviewView.tsx`. Verified by eye in
the interactive browser session; no automated test was added because
BusinessReviewView is unit-tested only indirectly (its data path, the
admin verify-queue response shape, is covered by QA-600.8).
