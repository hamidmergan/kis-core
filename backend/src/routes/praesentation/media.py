"""Reading routes: the state of a run, a preview picture, a drawn picture, the finished file."""

import io
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from src.dependencies import get_current_user
from src.features.praesentation import store
from src.features.praesentation.schemas import Slide
from src.i18n import get_locale, t
from src.routes.praesentation._shared import own_job
from src.utils.download_header import attachment

router = APIRouter(tags=["praesentation"])
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_SLIDE_ID = re.compile(r"^s\d+$")
_SLOT = re.compile(r"^(\d+|body)$")
# Wide enough for a card in the slide sketch, far below what the model draws.
_SKIZZE_PX = 640


def _bildplaetze(s: Slide) -> list[str]:
    """Every picture a slide asks for, named the way the store numbers them."""
    plaetze = [str(k) for k in range(len(s.images))]
    if s.body is not None and s.body.kind == "image":
        plaetze.append("body")
    return plaetze


@router.get("/praesentation/{job_uuid}")
def get_praesentation(job_uuid: str, current_user: dict = Depends(get_current_user),
                            locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    outline = store.load_outline(user_id, job_uuid)
    slides = store.load_slides(user_id, job_uuid)
    progress = json.loads(job["progress"]) if job.get("progress") else None
    bilder = {s.id: [p for p in _bildplaetze(s) if store.has_image(user_id, job_uuid, s.id, p)] for s in slides}
    return {
        "job_uuid": job_uuid,
        "status": job["status"],
        "progress": progress,
        "error": job.get("error_message"),
        "params": params.model_dump() if params else None,
        "outline": outline.model_dump() if outline else None,
        "slides": [s.model_dump() for s in slides],
        "previews": [s.id for s in slides if store.has_preview(user_id, job_uuid, s.id)],
        "images": bilder,
        "missing_images": [s.id for s in slides if len(bilder[s.id]) < len(_bildplaetze(s))],
        "has_deck": store.has_deck(user_id, job_uuid),
    }


@router.get("/praesentation/{job_uuid}/preview/{slide_id}.png")
def get_preview(job_uuid: str, slide_id: str, current_user: dict = Depends(get_current_user),
                      locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    if not _SLIDE_ID.match(slide_id):
        raise HTTPException(status_code=404)
    png = store.get_preview(job["user_id"], job_uuid, slide_id)
    if not png:
        raise HTTPException(status_code=404)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


def _verkleinert(data: bytes) -> tuple[bytes, str]:
    """The picture scaled down for a card, the original when it cannot be read."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as bild:
            bild.thumbnail((_SKIZZE_PX, _SKIZZE_PX))
            aus = io.BytesIO()
            bild.convert("RGB").save(aus, "JPEG", quality=82)
            return aus.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 - an unreadable picture still goes out as it was stored
        return data, "image/png"


@router.get("/praesentation/{job_uuid}/image/{slide_id}/{slot}")
def get_image(job_uuid: str, slide_id: str, slot: str, current_user: dict = Depends(get_current_user),
              locale: str = Depends(get_locale)):
    """One drawn picture as soon as it is stored, so the slide sketch fills while the run goes on."""
    job = own_job(job_uuid, current_user, locale)
    if not _SLIDE_ID.match(slide_id) or not _SLOT.match(slot):
        raise HTTPException(status_code=404)
    data = store.get_image(job["user_id"], job_uuid, slide_id, slot)
    if not data:
        raise HTTPException(status_code=404)
    inhalt, art = _verkleinert(data)
    return Response(content=inhalt, media_type=art, headers={"Cache-Control": "no-store"})


@router.get("/praesentation/{job_uuid}/download")
def download(job_uuid: str, current_user: dict = Depends(get_current_user),
                   locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    # Spec: the download opens only after "Fertigstellen", an in-progress deck must stay hidden.
    if job["status"] != "success":
        raise HTTPException(status_code=404, detail=t("praesentation.noDeck", locale))
    user_id = job["user_id"]
    data = store.get_deck(user_id, job_uuid)
    if not data:
        raise HTTPException(status_code=404, detail=t("praesentation.noDeck", locale))
    outline = store.load_outline(user_id, job_uuid)
    name = (re.sub(r"[^\w\s\-]", "", outline.title if outline else "").strip() or "Praesentation")[:80]
    return StreamingResponse(iter([data]), media_type=_PPTX, headers={
        "Content-Length": str(len(data)),
        "Content-Disposition": attachment(f"{name}.pptx"),
    })
