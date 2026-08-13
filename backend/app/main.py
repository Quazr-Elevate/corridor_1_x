from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import buyers, gstin, health, otp, pan, sellers

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
app.include_router(gstin.router)
app.include_router(pan.router)
app.include_router(otp.router)
app.include_router(sellers.router)
app.include_router(buyers.router)
