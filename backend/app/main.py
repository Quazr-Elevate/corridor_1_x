from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.email_module import EmailConfig
from app.email_module.send import configure as configure_email
from app.routers import (
    admin,
    auth,
    health,
    ifsc,
    me,
    onboarding,
    pincode,
    products,
    profile,
    public,
    reveals,
    verification,
)

app = FastAPI(title="Cor1x API", version="0.2.0")

# Wire the email module's defaults from settings once at import so every
# ``send_email()`` call site stays config-free. Outbox pinned under
# backend/ so files land in the same place regardless of uvicorn's cwd.
_EMAIL_OUTBOX = Path(__file__).resolve().parent.parent / "outbox"
configure_email(
    EmailConfig(
        provider=settings.email_provider,
        api_key=settings.email_api_key,
        from_address=settings.email_from,
        from_name=settings.email_from_name,
        reply_to=settings.email_reply_to or None,
        outbox_dir=_EMAIL_OUTBOX,
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Allow any localhost/127.0.0.1 with any port for dev ergonomics.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(me.router)
app.include_router(profile.router)
app.include_router(verification.router)
app.include_router(products.router)
app.include_router(reveals.router)
app.include_router(ifsc.router)
app.include_router(pincode.router)
app.include_router(public.router)
app.include_router(admin.router)

# Serve locally-stored uploads. Production swaps this for S3/R2/CloudFront.
# Anchor the path to backend/ so uvicorn can be launched from any cwd.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_ROOT.mkdir(exist_ok=True)
(UPLOAD_ROOT / "verification").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")
