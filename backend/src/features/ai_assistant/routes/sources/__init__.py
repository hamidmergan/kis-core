"""Source routes: upload, serve, PDF access."""
from fastapi import APIRouter

from ._upload import router as _upload_router
from ._link import router as _link_router
from ._streaming import router as _streaming_router
from ._pdf import router as _pdf_router
from ._rename import router as _rename_router
from ._chapters import router as _chapters_router

router = APIRouter()
router.include_router(_upload_router)
router.include_router(_link_router)
router.include_router(_streaming_router)
router.include_router(_pdf_router)
router.include_router(_rename_router)
router.include_router(_chapters_router)
