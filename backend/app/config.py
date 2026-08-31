from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env sits next to `backend/app/config.py`. Anchoring here means the file is
# picked up whether uvicorn is launched from the project root or from backend/.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), extra="ignore", case_sensitive=False
    )

    # Default: SQLite for dev. Swap for Postgres in production via env.
    database_url: str = "sqlite+aiosqlite:///./cor1x.db"

    # Comma-separated list, e.g. "http://localhost:3000,https://cor1x.com"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Masters India (GSTIN search)
    masters_india_access_token: str | None = None

    # MSG91 (OTP / SMS)
    msg91_auth_key: str | None = None
    msg91_template_id: str | None = None

    # Admin console — single-operator MVP. Keep the hash out of git; put
    # `ADMIN_PASSWORD_HASH` in .env. Generate with:
    #     python -c "import bcrypt; print(bcrypt.hashpw(b'yourpass', bcrypt.gensalt()).decode())"
    admin_email: str = "admin@cor1x.local"
    admin_password_hash: str = ""
    # Session cookie signing secret. Change in prod via env var.
    admin_session_secret: str = "dev-only-admin-secret-change-me"
    admin_session_max_age_hours: int = 12

    # User session cookie signing secret (cor1x_session + cor1x_verified_phone).
    # ROTATE in prod via env var — leaked secret means every session token is
    # forgeable. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
    session_secret: str = "dev-only-session-secret-change-me"

    # When true, rate limits are relaxed (dev/testing). Off for real prod.
    # NOTE: this no longer controls the cookie Secure/SameSite flags — that is
    # `cross_site_cookies` below, so a testing deploy can keep DEBUG=true (OTP
    # stub + loose limits) while still issuing cross-site cookies over HTTPS.
    debug: bool = True

    # Set true on ANY HTTPS deployment where the frontend and backend are on
    # different sites (e.g. two *.up.railway.app subdomains). Issues cookies as
    # `SameSite=None; Secure` so they flow frontend→API across sites. Leave
    # false for local http://localhost dev (Secure cookies need HTTPS).
    # Independent of DEBUG on purpose — a testing env is HTTPS + cross-site but
    # still wants the dev OTP stub and relaxed limits.
    cross_site_cookies: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Normalize DATABASE_URL for the async stack.

        1. Coerce Postgres URLs to the asyncpg driver. Managed providers
           (Railway, Heroku, Supabase, …) hand out `postgres://` or
           `postgresql://`, which SQLAlchemy pairs with the *sync* psycopg2
           driver — but the whole app (and Alembic) runs on an async engine,
           which needs `postgresql+asyncpg://`. Without this, `alembic upgrade
           head` fails at boot ("the asyncio extension requires an async
           driver"), the `&&` blocks uvicorn, and the healthcheck sees nothing.
           `?sslmode=`/`?ssl=` query args (libpq-style) are stripped — asyncpg
           doesn't accept them; it uses TLS automatically for managed hosts.
        2. Anchor relative SQLite paths to backend/ so the dev DB is found
           regardless of the launch cwd.
        """
        url = self.database_url

        if url.startswith("postgres://") or url.startswith("postgresql://"):
            # scheme swap → asyncpg
            url = url.split("://", 1)[1]
            url = f"postgresql+asyncpg://{url}"
        if url.startswith("postgresql+asyncpg://") and "?" in url:
            # drop libpq-only query params asyncpg rejects (e.g. sslmode)
            url = url.split("?", 1)[0]
        if url.startswith("postgresql+asyncpg://"):
            return url

        prefix = "sqlite+aiosqlite:///./"
        if url.startswith(prefix):
            backend_dir = Path(__file__).resolve().parent.parent
            return f"sqlite+aiosqlite:///{backend_dir / url[len(prefix):]}"
        return url


settings = Settings()
