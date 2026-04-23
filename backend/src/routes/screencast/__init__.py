"""Screencast-Routen-Paket: fügt alle Sub-Router zu einem einzigen `router` zusammen.

Historisch hieß dieses Modul `src/routes/screencast.py` und exportierte `router`.
Externe Importe sollen unverändert funktionieren (`from src.routes import screencast;
screencast.router`), daher wird hier ein aggregierter Router bereitgestellt."""

from fastapi import APIRouter

from src.routes.screencast.audio import router as _audio_router
from src.routes.screencast.media import router as _media_router
from src.routes.screencast.render import router as _render_router
from src.routes.screencast.resume import router as _resume_router
from src.routes.screencast.scripts import router as _scripts_router
from src.routes.screencast.translate import router as _translate_router

router = APIRouter()
router.include_router(_translate_router)
router.include_router(_scripts_router)
router.include_router(_media_router)
router.include_router(_resume_router)
router.include_router(_render_router)
router.include_router(_audio_router)

__all__ = ["router"]
