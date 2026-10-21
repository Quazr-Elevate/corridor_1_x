"""GET /health — Railway healthcheck. 200 {"status":"ok"} when the DB
answers ``SELECT 1``; 503 otherwise."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.db import ping_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    if await ping_db():
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error", "detail": "database unavailable"}, status_code=503)
