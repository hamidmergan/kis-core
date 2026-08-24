"""Job status and download endpoints for async Celery tasks.

Aggregates sub-routers in the original registration order so FastAPI route
priority is preserved (specific paths like /my and /check/* must precede
/{job_uuid} catch-alls).
"""

from fastapi import APIRouter

from src.routes.jobs._cancel import router as _cancel_router
from src.routes.jobs._check import router as _check_router
from src.routes.jobs._download import router as _download_router
from src.routes.jobs._list import router as _list_router
from src.routes.jobs._retry import router as _retry_router
from src.routes.jobs._status import router as _status_router
from src.routes.jobs._video import router as _video_router


router = APIRouter(prefix="/jobs", tags=["jobs"])

# Order matters: specific paths first, {job_uuid} catch-alls last
router.include_router(_check_router)       # /check/{tool_group}
router.include_router(_list_router)        # /my, /stream
router.include_router(_retry_router)       # /{job_uuid}/retry
router.include_router(_cancel_router)      # /{job_uuid}/cancel, DELETE /{job_uuid}
router.include_router(_status_router)      # GET /{job_uuid}
router.include_router(_video_router)       # /{job_uuid}/video
router.include_router(_download_router)    # /{job_uuid}/download, /pptx, /bundle


__all__ = ["router"]
