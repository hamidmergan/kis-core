"""Bundles the podcast routes into one router behind the tool right."""

from fastapi import APIRouter, Depends

from src.dependencies_rbac import require_tool_access
from src.routes.material_measure import measure_router
from src.routes.podcast.media import router as _media_router
from src.routes.podcast.params import router as _params_router
from src.routes.podcast.render import router as _render_router
from src.routes.podcast.script import router as _script_router
from src.routes.podcast.start import router as _start_router

router = APIRouter(dependencies=[Depends(require_tool_access("podcast"))])
router.include_router(_start_router)
router.include_router(measure_router("podcast"))
router.include_router(_render_router)
router.include_router(_media_router)
router.include_router(_params_router)
# Last: its "/podcast/{job_uuid}" must not swallow "/podcast/start".
router.include_router(_script_router)

__all__ = ["router"]
