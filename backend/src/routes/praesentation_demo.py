"""The presentation demo, a finished run from files, without compute and without a job."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.features.praesentation import store
from src.features.praesentation.schemas import Slide
from src.i18n import get_locale, t
from src.routes.praesentation.media import _SLIDE_ID, _SLOT, _bildplaetze, _verkleinert
from src.utils.download_header import attachment

router = APIRouter(
    tags=["praesentation-demo"],
    dependencies=[Depends(require_tool_access("praesentation"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "praesentation"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _laden(locale: str) -> dict:
    pfad = DEMO_DIR / "ansicht.json"
    if not pfad.exists():
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return json.loads(pfad.read_text(encoding="utf-8"))


@router.get("/praesentation-demo/available")
def demo_available(_: dict = Depends(get_current_user)):
    """Whether a prepared run is there, the tool page only offers the demo then."""
    return {"available": (DEMO_DIR / "ansicht.json").exists() and (DEMO_DIR / store.DECK_FILE).exists()}


@router.get("/praesentation-demo/ansicht")
def demo_ansicht(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The finished run as the real view reports it, plus the material it was made from."""
    daten = _laden(locale)
    slides = [Slide.model_validate(s) for s in daten.get("slides", [])]
    bilder = {s.id: [p for p in _bildplaetze(s) if (DEMO_DIR / store.image_name(s.id, p)).exists()]
              for s in slides}
    return {
        "job_uuid": "demo",
        "status": "success",
        "progress": None,
        "error": None,
        "params": daten.get("params"),
        "outline": daten.get("outline"),
        "slides": [s.model_dump() for s in slides],
        "previews": [s.id for s in slides if (DEMO_DIR / store.preview_name(s.id)).exists()],
        "images": bilder,
        "missing_images": [s.id for s in slides if len(bilder[s.id]) < len(_bildplaetze(s))],
        "has_deck": (DEMO_DIR / store.DECK_FILE).exists(),
        "workspace": daten.get("workspace", ""),
        "files": daten.get("dateien", []),
    }


@router.get("/praesentation-demo/preview/{slide_id}.png")
def demo_preview(slide_id: str, _: dict = Depends(get_current_user)):
    datei = DEMO_DIR / store.preview_name(slide_id)
    if not _SLIDE_ID.match(slide_id) or not datei.exists():
        raise HTTPException(status_code=404)
    return FileResponse(datei, media_type="image/png")


@router.get("/praesentation-demo/image/{slide_id}/{slot}")
def demo_image(slide_id: str, slot: str, _: dict = Depends(get_current_user)):
    """One drawn picture, scaled down for the sketch like in the real run."""
    if not _SLIDE_ID.match(slide_id) or not _SLOT.match(slot):
        raise HTTPException(status_code=404)
    datei = DEMO_DIR / store.image_name(slide_id, slot)
    if not datei.exists():
        raise HTTPException(status_code=404)
    inhalt, art = _verkleinert(datei.read_bytes())
    return Response(content=inhalt, media_type=art)


@router.get("/praesentation-demo/download")
def demo_download(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    datei = DEMO_DIR / store.DECK_FILE
    if not datei.exists():
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    titel = (_laden(locale).get("outline") or {}).get("title", "")
    name = (re.sub(r"[^\w\s\-]", "", titel).strip() or "Praesentation")[:80]
    return FileResponse(datei, media_type=_PPTX, headers={"Content-Disposition": attachment(f"{name}.pptx")})
