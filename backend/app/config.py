from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Default: SQLite for dev. Swap for Postgres in production via env.
    database_url: str = "sqlite+aiosqlite:///./cor1x.db"

    # Comma-separated list, e.g. "http://localhost:3000,https://cor1x.com"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Masters India (GSTIN search)
    masters_india_access_token: str | None = None

    # MSG91 (OTP / SMS)
    msg91_auth_key: str | None = None
    msg91_template_id: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
