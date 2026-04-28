"""Admin routes package: aggregates all sub-routers under the `/admin` prefix.

Historically this module was named `src/routes/admin.py` and exported `router`
with prefix="/admin". External imports (`from src.routes import admin;
admin.router`) continue to work unchanged."""

from fastapi import APIRouter

from src.routes.admin.jobs import router as _jobs_router
from src.routes.admin.maintenance import router as _maintenance_router
from src.routes.admin.prompts import router as _prompts_router
from src.routes.admin.quota import router as _quota_router
from src.routes.admin.settings import router as _settings_router
from src.routes.admin.stats import router as _stats_router
from src.routes.admin.tools import router as _tools_router
from src.routes.admin.users import router as _users_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(_settings_router)
router.include_router(_maintenance_router)
router.include_router(_tools_router)
router.include_router(_users_router)
router.include_router(_stats_router)
router.include_router(_jobs_router)
router.include_router(_prompts_router)
router.include_router(_quota_router)

__all__ = ["router"]
