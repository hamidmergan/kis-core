"""The presentation router, every route behind the tool right."""

from fastapi import APIRouter, Depends

from src.dependencies_rbac import require_tool_access
from src.routes.praesentation.media import router as _media_router
from src.routes.praesentation.outline import router as _outline_router
from src.routes.praesentation.slides import router as _slides_router
from src.routes.praesentation.start import router as _start_router
from src.routes.praesentation.vorlagen import router as _vorlagen_router

router = APIRouter(dependencies=[Depends(require_tool_access("praesentation"))])
router.include_router(_start_router)
router.include_router(_vorlagen_router)
router.include_router(_outline_router)
router.include_router(_slides_router)
# Last: its "/praesentation/{job_uuid}" must not swallow "/praesentation/start" or "/praesentation/vorlagen".
router.include_router(_media_router)

__all__ = ["router"]
