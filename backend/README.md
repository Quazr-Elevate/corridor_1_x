# Cor1x Backend

FastAPI + SQLAlchemy 2.0 (async) + Alembic. **SQLite for local dev; swap to Postgres in production** — no code changes, just an env var.

## Layout

```
backend/
├── alembic/                # migrations
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── app/
│   ├── main.py             # FastAPI app + CORS + routers
│   ├── config.py           # Settings from .env
│   ├── db.py               # async engine + session
│   ├── validators.py       # GSTIN / PAN / phone / email regex
│   ├── models/             # SQLAlchemy models (5 tables)
│   ├── schemas/            # Pydantic request/response (camelCase aliases)
│   ├── providers/          # External APIs — Masters India, MSG91
│   └── routers/            # HTTP endpoints
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Quickstart (SQLite dev — zero DB setup)

```bash
cd backend

# 1. Virtualenv
python -m venv .venv
.venv\Scripts\activate               # Windows PowerShell
# source .venv/bin/activate           # macOS/Linux

# 2. Install deps
pip install -r requirements.txt

# 3. Configure env
copy .env.example .env               # Windows
# cp .env.example .env                # macOS/Linux
# Nothing to edit — SQLite is the default and needs no config.

# 4. Create tables
alembic upgrade head
# → creates backend/cor1x.db with the 5 tables (users, identities, sellers, buyers, otps)

# 5. Start the API
uvicorn app.main:app --reload --port 8000
```

API docs live at http://localhost:8000/docs while running.

## Switching to Postgres (production)

When you're ready:

1. Provision Postgres (Docker, RDS, Supabase, whatever).
2. Edit `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/cor1x
   ```
3. Run `alembic upgrade head` against the new DB.

The same migration and models work on both — `sa.Uuid`, `sa.Enum`, and the partial index are all portable.

## Endpoints

| Method | Path                | Purpose                              |
|--------|---------------------|--------------------------------------|
| GET    | `/health`           | Liveness check                       |
| GET    | `/gstin/{gstin}`    | Masters India GST search             |
| GET    | `/pan/{pan}`        | PAN lookup (stubbed — swap for real) |
| POST   | `/otp/send`         | MSG91 OTP send                       |
| POST   | `/otp/verify`       | MSG91 OTP verify                     |
| POST   | `/sellers`          | Create a seller (user + identity)    |

## Stub-fallback behavior

If a vendor env var is missing, the corresponding provider serves canned data
so you can develop the whole flow without accounts:

- **GSTIN**: any valid 15-char GSTIN returns "Kaveri Foods Private Limited" data.
- **OTP send**: returns a fake `otpId` and hint "Use 123456".
- **OTP verify**: `123456` succeeds; anything else fails.

Fill in real credentials in `.env` when you're ready; the code switches automatically.

## Adding a migration

```bash
alembic revision -m "add certifications table"
# edit the new file in alembic/versions/
alembic upgrade head
```
