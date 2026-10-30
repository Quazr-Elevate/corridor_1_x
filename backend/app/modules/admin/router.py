"""Admin console — every route except /admin/login requires the signed
``cor1x_admin`` cookie (``AdminEmail`` dependency)."""
from fastapi import APIRouter

from app.modules.admin import auth, dashboard, docs, kyb_types, users

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(users.router)
router.include_router(docs.router)
router.include_router(kyb_types.router)
