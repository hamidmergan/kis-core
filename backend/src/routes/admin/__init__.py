"""Bundles all sub-routes under the /admin prefix."""

from fastapi import APIRouter

from src.routes.admin.access_codes import router as _access_codes_router
from src.routes.admin.diagnosis_plan import router as _diagnosis_plan_router
from src.routes.admin.evaluation import router as _evaluation_router
from src.routes.admin.feedback import router as _feedback_router
from src.routes.admin.impersonation import router as _impersonation_router
from src.routes.admin.invites import router as _invites_router
from src.routes.admin.jobs import router as _jobs_router
from src.routes.admin.load import router as _load_router
from src.routes.admin.accounts import router as _accounts_router
from src.routes.admin.maintenance import router as _maintenance_router
from src.routes.admin.model_windows import router as _model_windows_router
from src.routes.admin.pools import router as _pools_router
from src.routes.admin.providers import router as _providers_router
from src.routes.admin.quota import router as _quota_router
from src.routes.admin.roles import router as _roles_router
from src.routes.admin.settings import router as _settings_router
from src.routes.admin.stats import router as _stats_router
from src.routes.admin.tools import router as _tools_router
from src.routes.admin.users import router as _users_router

router = APIRouter(prefix="/admin")
router.include_router(_access_codes_router)
router.include_router(_settings_router)
router.include_router(_diagnosis_plan_router)
router.include_router(_maintenance_router)
router.include_router(_pools_router)
router.include_router(_tools_router)
router.include_router(_users_router)
router.include_router(_stats_router)
router.include_router(_jobs_router)
router.include_router(_load_router)
router.include_router(_accounts_router)
router.include_router(_invites_router)
router.include_router(_providers_router)
router.include_router(_model_windows_router)
router.include_router(_quota_router)
router.include_router(_roles_router)
router.include_router(_impersonation_router)
router.include_router(_feedback_router)
router.include_router(_evaluation_router)

__all__ = ["router"]
