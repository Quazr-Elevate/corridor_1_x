"""Application settings, loaded from environment variables / backend/.env.

Every path-like setting is anchored to the backend/ directory so the app
behaves the same whether uvicorn is launched from backend/ or from the repo
root (``--app-dir backend``).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: backend/ — the anchor for every relative path (DB file, uploads, outbox).
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = BACKEND_DIR / ".env"


def resolve_backend_path(value: str | Path) -> Path:
    """Absolute paths pass through; relative ones are anchored to backend/."""
    p = Path(value)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), extra="ignore", case_sensitive=False
    )

    # ─── Database ────────────────────────────────────────────────
    # SQLite for local dev; Postgres (postgres:// URLs are coerced to
    # asyncpg) in production.
    database_url: str = "sqlite+aiosqlite:///./cor1x.db"
    # Postgres: any single statement running longer than this is cancelled,
    # so a stuck query can't hold a pooled connection forever. 0 = no limit.
    db_statement_timeout_ms: int = 15000

    # ─── Web ─────────────────────────────────────────────────────
    # Comma-separated list, e.g. "http://localhost:3000,https://cor1x.com"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Public base URL of the frontend (used to build links in emails and
    # redirects). Defaults to the first CORS origin.
    frontend_base_url: str = ""

    # When true: relaxed rate limits and the dev-only ``devCode`` in the
    # signup-code response. Must be false in real production.
    debug: bool = True

    # Set true on ANY HTTPS deployment where the frontend and backend are on
    # different sites (e.g. two *.up.railway.app subdomains) so cookies are
    # issued as `SameSite=None; Secure`. Leave false for http://localhost.
    cross_site_cookies: bool = False

    # ─── Logging ─────────────────────────────────────────────────
    log_level: str = "INFO"
    # "kv" (key=value, human friendly) or "json" (one JSON object per line).
    log_format: str = "kv"

    # ─── Admin console ───────────────────────────────────────────
    # Single-operator MVP. Generate the hash with:
    #   python -c "import bcrypt; print(bcrypt.hashpw(b'yourpass', bcrypt.gensalt()).decode())"
    admin_email: str = "admin@cor1x.local"
    admin_password_hash: str = ""
    admin_session_secret: str = "dev-only-admin-secret-change-me"
    admin_session_max_age_hours: int = 12

    # ─── User sessions ───────────────────────────────────────────
    # Signs the cor1x_session cookie and keys email-code hashes. ROTATE in prod.
    session_secret: str = "dev-only-session-secret-change-me"

    # ─── KYB field encryption (app/core/crypto.py) ───────────────
    # Comma-separated ``version:base64key`` list of 32-byte AES keys. The
    # highest version encrypts new values; every listed version decrypts.
    # Generate a key: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    # Required when DEBUG=false; development falls back to a marked local key.
    kyb_enc_keys: str = ""
    # Separate base64 32-byte key for the duplicate-check hash (value_hash).
    kyb_hash_key: str = ""

    # ─── Email (app/integrations/email) ──────────────────────────
    email_provider: str = "console"  # console | resend | brevo
    email_api_key: str = ""
    email_from: str = "enquiry@corridor1x.com"
    email_from_name: str = "Corridor One X"
    email_reply_to: str = ""
    email_outbox_dir: str = "outbox"
    email_max_attempts: int = 3
    email_timeout_sec: float = 10.0

    # ─── SMS (app/integrations/sms) — not wired to endpoints yet ──
    sms_provider: str = "console"  # console | msg91
    sms_outbox_dir: str = "outbox/sms"
    sms_msg91_auth_key: str = ""
    sms_msg91_otp_template_id: str = ""
    sms_msg91_flow_template_id: str = ""
    sms_msg91_flow_var_name: str = "message"
    sms_default_country_code: str = "91"
    sms_otp_length: int = 6
    sms_otp_expiry_minutes: int = 10

    # ─── Storage (app/integrations/storage) ──────────────────────
    storage_backend: str = "local"  # local | s3
    storage_dir: str = "uploads"  # local backend root (relative → backend/)
    storage_s3_bucket: str = ""
    storage_s3_region: str = ""
    storage_s3_endpoint_url: str = ""  # e.g. Cloudflare R2 endpoint
    storage_s3_access_key_id: str = ""
    storage_s3_secret_access_key: str = ""

    # ─── Rate limiting (app/ratelimit) ───────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_backend: str = "memory"  # memory (redis: planned)
    rate_limit_redis_url: str = ""
    # Limits are multiplied by this factor when DEBUG=true (still enforced).
    rate_limit_debug_multiplier: int = 10
    # How many proxies we run in front of the API (each appends to
    # X-Forwarded-For). The client IP is read that many entries from the
    # RIGHT, so a client-supplied header can't spoof it. 0 = ignore the
    # header and use the socket peer (local dev, direct calls).
    # Railway edge → API: 1. Railway edge → frontend /api proxy → API: 2.
    rate_limit_trusted_proxies: int = 0

    # ─── Exchange rates (app/integrations/fx) ────────────────────
    # Background refresh in the API process (on start when today's rates
    # are missing, then every FX_REFRESH_HOURS). scripts/refresh_rates.py
    # does the same from cron.
    fx_enabled: bool = True
    # Tried in order per currency: frankfurter | fawazahmed0 | static
    fx_providers: str = "frankfurter,fawazahmed0"
    # Listing + display currencies. Must match ck_users_display_currency.
    fx_supported_currencies: str = "INR,AED,USD"
    fx_refresh_hours: float = 24
    fx_timeout_sec: float = 10.0
    fx_max_attempts: int = 3
    # A fetched rate that moves more than this vs the last stored one is
    # rejected (logged; the last rate is kept).
    fx_max_change_pct: float = 20.0

    # ─── Lookups (pincode / IFSC) ────────────────────────────────
    # When true, lookups return canned data instead of calling the
    # upstream APIs (offline dev). Never enable in production.
    lookups_stub: bool = False

    # ─── Derived ─────────────────────────────────────────────────

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def frontend_base(self) -> str:
        base = self.frontend_base_url.strip() or (
            self.cors_origin_list[0] if self.cors_origin_list else "http://localhost:3000"
        )
        return base.rstrip("/")

    @property
    def fx_provider_list(self) -> tuple[str, ...]:
        return tuple(p.strip().lower() for p in self.fx_providers.split(",") if p.strip())

    @property
    def fx_currency_list(self) -> tuple[str, ...]:
        """Supported ISO 4217 codes, upper-cased, USD always included."""
        codes = [c.strip().upper() for c in self.fx_supported_currencies.split(",") if c.strip()]
        if "USD" not in codes:
            codes.append("USD")
        return tuple(dict.fromkeys(codes))

    @property
    def storage_path(self) -> Path:
        return resolve_backend_path(self.storage_dir)

    @property
    def email_outbox_path(self) -> Path:
        return resolve_backend_path(self.email_outbox_dir)

    @property
    def sms_outbox_path(self) -> Path:
        return resolve_backend_path(self.sms_outbox_dir)

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def resolved_database_url(self) -> str:
        """Normalize DATABASE_URL for the async stack.

        1. Coerce Postgres URLs to the asyncpg driver (managed providers hand
           out ``postgres://``/``postgresql://``) and strip libpq-only query
           params like ``sslmode`` that asyncpg rejects.
        2. Anchor relative SQLite paths to backend/.
        """
        url = self.database_url
        if url.startswith("postgres://") or url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url.split("://", 1)[1]
        if url.startswith("postgresql+asyncpg://"):
            return url.split("?", 1)[0]

        prefix = "sqlite+aiosqlite:///./"
        if url.startswith(prefix):
            return f"sqlite+aiosqlite:///{BACKEND_DIR / url[len(prefix):]}"
        return url


settings = Settings()
