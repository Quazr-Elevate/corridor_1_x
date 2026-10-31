"""Admin console — every route except /admin/login and /admin/logout
requires an admin session with a permission (``deps.require``)."""
from fastapi import APIRouter

from app.modules.admin import admins, auth, dashboard, docs, kyb_types, users

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(users.router)
router.include_router(docs.router)
router.include_router(kyb_types.router)
router.include_router(kyb_types.countries_router)
router.include_router(admins.router)
