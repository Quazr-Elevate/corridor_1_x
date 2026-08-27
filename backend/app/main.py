from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    admin,
    auth,
    buyers,
    gstin,
    health,
    ifsc,
    me,
    otp,
    pan,
    pincode,
    products,
    profile,
    sellers,
)

app = FastAPI(title="Cor1x API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Allow any localhost/127.0.0.1 with any port (dev ergonomics — a browser
    # visiting http://127.0.0.1:3000 vs http://localhost:3000 is a different
    # CORS origin, and we don't want to chase which one it picked). Safe in
    # prod because prod origins are never localhost.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(gstin.router)
app.include_router(pan.router)
app.include_router(otp.router)
app.include_router(sellers.router)
app.include_router(buyers.router)
app.include_router(me.router)
app.include_router(profile.router)
app.include_router(products.router)
app.include_router(ifsc.router)
app.include_router(pincode.router)
app.include_router(admin.router)

# Serve locally-stored uploads. Production swaps this for S3/R2/CloudFront.
UPLOAD_ROOT = Path("uploads")
UPLOAD_ROOT.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")
