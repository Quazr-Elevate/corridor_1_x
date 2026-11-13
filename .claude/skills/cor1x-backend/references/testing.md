# Testing

Tests are how a row proves it's done and how the next person changes code
without fear. They run with pytest and httpx against the real ASGI app on a
temporary SQLite database: no mocks of our own code, real routes, real
middleware, real constraints.

## Setup

`tests/conftest.py` creates the schema once per session and cleans every table
between tests (`_schema`, `_clean`, both autouse). Integrations run on their
test doubles: the console email outbox, stubbed lookups, local storage.

| Fixture or helper | Gives you |
|---|---|
| `client` | An httpx client for one trader |
| `make_client()` | A fresh anonymous client: the public, or a second trader |
| `admin_client` | A signed-in super admin |
| `signup_and_login(c, email)` | The full email-code sign-up on a client |
| `fill_mandatory(c, n=1)` | Completes the mandatory KYB items |
| `set_status(user_id, status)` | Puts a business straight into a verification state |
| `sent_emails(to)` / `code_from_email(to)` | Reads the email outbox |
| `png_bytes(size)` | A valid tiny PNG for upload tests |

Use realistic business emails in tests, as the suite does (`ph@kaverifoods.in`),
not `test@test.com`.

## What every row adds

| Test | Proves | Example |
|---|---|---|
| **Rule** | The service enforces the rule the row is about, including the edge its *Done when* names | A published listing re-enters review on edit |
| **Happy path** | The route returns the documented shape and status | 201 with the listing in `draft` |
| **Refusal** | The main wrong input gets the right status *and* message | 409 "A published listing can't be moved to draft." |
| **Access** | A stranger gets **404**; the wrong admin role gets **403**; anonymous gets **401** | Another business can't submit your listing |
| **Migration** | Existing rows survive and are backfilled (only when data moves) | `test_migration_0026.py` |
| **Journey** | `tests/qa/` gains a step when a user flow changes | Sign up → list → review → market |

## How the existing tests are written

```python
async def test_photo_upload_and_serving(client, make_client):
    await signup_and_login(client, "ph@kaverifoods.in")
    r = await client.post(
        "/products/upload-photo", files={"file": ("x.png", b"<html>evil</html>", "image/png")}
    )
    assert r.status_code == 415
    url = await _photo(client)
    assert url.startswith("/uploads/products/") and url.endswith(".png")
    r = await make_client().get(url)  # public
    assert r.headers["x-content-type-options"] == "nosniff"
    assert (await client.get("/uploads/products/../../cor1x.db")).status_code == 404
```

What to copy:
- **The name states the behaviour**: `test_market_visibility_is_business_level`,
  `test_reveal_limit_is_per_business`, `test_contact_reveal_gates_and_idempotency`.
- **The hostile case sits next to the normal one**: wrong content type, path
  traversal, another business. A security property is tested, not assumed.
- **Assertions check the body, the headers and the side effect**, not only the
  status code.
- **One test can walk a short story** (refused → allowed → visible) when the
  steps depend on each other. Don't split it into fragments that each re-create
  the world.

## Rules

- A test that fails tells you something. Fix the cause. Never skip, `xfail`,
  loosen or delete a test to get green without saying so in the PR, with the reason.
- Never assert on wording you'll want to change freely. Assert on `code` once
  the error contract lands; until then, assert the exact `detail` only where the
  message *is* the behaviour.
- No sleeping and no wall-clock dependence. Time-based rules take an injectable
  clock or are tested through `core/time.py`.
- No network. Integrations are swapped through `app.dependency_overrides` or the
  stub settings.
- The route-matrix test (every `/admin` route declares a permission) and the
  cross-business tests are the security floor. They must keep passing.
- From M2, the response-guard test (no vault field in any external response)
  joins that floor.

## Migration tests

When a migration moves or backfills data, add `tests/test_migration_00NN.py` in
the style of `test_migration_0019.py` … `0023.py`: build the schema at the
previous revision, insert representative rows (including the awkward ones:
deleted, unverified, null), upgrade, and assert the result. Postgres-specific
behaviour gets checked on a Postgres copy before deploy (CX-003).

## Commands

```bash
cd backend && .venv/bin/pytest -q                       # everything
cd backend && .venv/bin/pytest tests/test_catalog.py -q  # one file
cd backend && .venv/bin/pytest -k reveal -q              # by name
cd backend && .venv/bin/pip-audit                        # dependency advisories
```

On Windows use `.venv\Scripts\pytest`. Report the count in the PR and commit
body: `Tests: 241 passing (+3)`.

## Reporting results

Say what ran and what came out. "All 241 tests pass" only after running them in
this change. If you couldn't run them (no venv, no database), say exactly that
and what you'd expect, never imply they passed.
