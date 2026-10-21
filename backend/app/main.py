"""App factory: logging, integrations, middleware, error handlers, routers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, settings
from app.core.db import engine
from app.core.csrf import CSRFOriginMiddleware
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.integrations import email as email_integration
from app.integrations.fx import FxConfig, configure_fx
from app.integrations.sms import SmsConfig, configure_sms
from app.integrations.storage import LocalStorage, S3Config, S3Storage, configure_storage
from app.modules.accounts.router import me_router, onboarding_router
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import products_router, public_router, uploads_router
from app.modules.fx.router import router as fx_router
from app.modules.fx.scheduler import FxRefresher
from app.modules.health.router import router as health_router
from app.modules.lookups.router import router as lookups_router
from app.modules.verification.router import router as verification_router
from app.ratelimit import MemoryRateLimitBackend, RateLimiter, configure_limiter

log = logging.getLogger("app")


def configure_integrations(s: Settings) -> None:
    """Wire the app-agnostic integration modules from settings."""
    email_integration.configure(
        email_integration.EmailConfig(
            provider=s.email_provider,
            api_key=s.email_api_key,
            from_address=s.email_from,
            from_name=s.email_from_name,
            reply_to=s.email_reply_to or None,
            outbox_dir=s.email_outbox_path,
            http_timeout_sec=s.email_timeout_sec,
            max_attempts=s.email_max_attempts,
        )
    )
    configure_sms(
        SmsConfig(
            provider=s.sms_provider,
            outbox_dir=s.sms_outbox_path,
            default_country_code=s.sms_default_country_code,
            otp_length=s.sms_otp_length,
            otp_expiry_minutes=s.sms_otp_expiry_minutes,
            msg91_auth_key=s.sms_msg91_auth_key,
            msg91_otp_template_id=s.sms_msg91_otp_template_id,
            msg91_flow_template_id=s.sms_msg91_flow_template_id,
            msg91_flow_var_name=s.sms_msg91_flow_var_name,
        )
    )
    configure_fx(
        FxConfig(
            providers=s.fx_provider_list,
            http_timeout_sec=s.fx_timeout_sec,
            max_attempts=s.fx_max_attempts,
        )
    )
    if s.storage_backend.strip().lower() == "s3":
        configure_storage(
            S3Storage(
                S3Config(
                    bucket=s.storage_s3_bucket,
                    region=s.storage_s3_region,
                    endpoint_url=s.storage_s3_endpoint_url,
                    access_key_id=s.storage_s3_access_key_id,
                    secret_access_key=s.storage_s3_secret_access_key,
                )
            )
        )
    else:
        configure_storage(LocalStorage(s.storage_path))

    if s.rate_limit_backend.strip().lower() != "memory":
        log.warning("RATE_LIMIT_BACKEND=%s is not implemented; using in-memory", s.rate_limit_backend)
    configure_limiter(
        RateLimiter(
            MemoryRateLimitBackend(),
            multiplier=s.rate_limit_debug_multiplier if s.debug else 1,
            enabled=s.rate_limit_enabled,
        ),
        trusted_proxies=s.rate_limit_trusted_proxies,
    )


def _lifespan_for(s: Settings):
    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        # Daily exchange-rate refresh: a background task, never on a request.
        refresher = FxRefresher(s.fx_refresh_hours) if s.fx_enabled else None
        if refresher is not None:
            refresher.start()
        try:
            yield
        finally:
            if refresher is not None:
                await refresher.stop()
            await engine.dispose()

    return _lifespan


def create_app(s: Settings = settings) -> FastAPI:
    configure_logging(s.log_level, s.log_format)
    configure_integrations(s)

    app = FastAPI(title="Cor1x API", version="0.3.0", lifespan=_lifespan_for(s))
    register_exception_handlers(app)

    # Innermost: blocks cross-site state-changing requests (see core/csrf.py).
    # Added before CORS so CORS (outer) still decorates its 403 responses.
    app.add_middleware(
        CSRFOriginMiddleware,
        trusted_origins=[*s.cors_origin_list, s.frontend_base],
        allow_localhost=s.debug,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        # Any localhost/127.0.0.1 port, for dev ergonomics.
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)

    for router in (
        health_router,
        auth_router,
        onboarding_router,
        me_router,
        verification_router,
        products_router,
        public_router,
        fx_router,
        uploads_router,
        lookups_router,
        admin_router,
    ):
        app.include_router(router)
    return app


app = create_app()
