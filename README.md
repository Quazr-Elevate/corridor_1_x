# corridor_1_x

Cor1x — a verified B2B agri marketplace for the India ⇄ Gulf corridor.

* `backend/` — FastAPI + SQLAlchemy 2.0 (async) + Alembic ([README](backend/README.md))
* `frontend/` — Next.js 14 (App Router) + Tailwind
* `docs/` — data model, feature catalogue, security review, test scenarios

## Tests

```bash
./scripts/e2e.sh
```

That boots a throwaway stack (its own database, email outbox and storage
dir — nothing real is touched), runs the backend unit/API suite, the
backend journey suite, the frontend typecheck, lint and build, and finally
the Playwright browser journeys, then prints a pass/fail summary.

Narrower runs:

```bash
./scripts/e2e.sh backend
```

```bash
./scripts/e2e.sh frontend -- --grep @market
```

Every scenario has a stable ID and is listed in
[`docs/testing/SCENARIOS.md`](docs/testing/SCENARIOS.md).
