# Frontend end-to-end tests

Playwright specs that drive a real browser against a real Next.js build
talking to a real backend. Nothing is mocked.

Run them with the repo-level runner, which boots the whole stack:

```bash
./scripts/e2e.sh frontend
```

Against a stack you already have running:

```bash
E2E_BASE_URL=http://127.0.0.1:3100 \
E2E_API_URL=http://127.0.0.1:8001 \
E2E_ADMIN_EMAIL=... E2E_ADMIN_PASSWORD=... \
npx playwright test
```

Tags: `--grep @public`, `@auth`, `@dashboard`, `@admin`, `@responsive`.
Scenario IDs (`E2E-UI-…`) and what each covers: `docs/testing/SCENARIOS.md`.

* `support/api.ts` — seeds traders, lots and admin decisions through the
  backend API, so a spec only drives the UI it is actually testing.
* `support/ui.ts` — the browser helpers. Use `gotoReady`, `fillField` and
  `submitForm` rather than raw `page.goto` / `page.fill`: Next streams the
  HTML before React attaches, and typing in that window is dropped.
* The backend must run with `DEBUG=true` — the signup screen then shows
  the emailed code, which is how the signup scenario completes.

## First run on a new machine

`@playwright/test` is pinned so the runner and the browser stay in step.
Install the browser once:

```bash
npx playwright install chromium
```

(CI images that already ship Chromium can point at it with
`PLAYWRIGHT_BROWSERS_PATH`; `scripts/e2e.sh` defaults that to
`/opt/pw-browsers`.)
