"""Bundles the screencast routes into one router."""

from fastapi import APIRouter, Depends

from src.dependencies_rbac import require_tool_access
from src.routes.material_measure import measure_router
from src.routes.screencast.audio import router as _audio_router
from src.routes.screencast.einstellungen import router as _einstellungen_router
from src.routes.screencast.material import router as _material_router
from src.routes.screencast.media import router as _media_router
from src.routes.screencast.render import router as _render_router
from src.routes.screencast.resume import router as _resume_router
from src.routes.screencast.scripts import router as _scripts_router
from src.routes.screencast.translate import router as _translate_router

router = APIRouter(dependencies=[Depends(require_tool_access("screencast"))])
router.include_router(_translate_router)
router.include_router(_scripts_router)
router.include_router(_media_router)
router.include_router(_resume_router)
router.include_router(_render_router)
router.include_router(_audio_router)
router.include_router(_einstellungen_router)
router.include_router(_material_router)
router.include_router(measure_router("screencast"))

__all__ = ["router"]
