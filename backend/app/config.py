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

    # When true, cookies are set with Secure=false (dev over http://) and rate
    # limits are relaxed. Off in production.
    debug: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """SQLite paths are relative to the process cwd unless rewritten. Anchor
        `sqlite+aiosqlite:///./name.db` to backend/ so uvicorn works whether it's
        launched from the project root or from backend/."""
        url = self.database_url
        prefix = "sqlite+aiosqlite:///./"
        if url.startswith(prefix):
            backend_dir = Path(__file__).resolve().parent.parent
            return f"sqlite+aiosqlite:///{backend_dir / url[len(prefix):]}"
        return url


settings = Settings()
