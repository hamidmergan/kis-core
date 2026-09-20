"""Reading routes: the state of a run, a preview picture, the finished file."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from src.dependencies import get_current_user
from src.features.praesentation import store
from src.i18n import get_locale, t
from src.routes.praesentation._shared import own_job

router = APIRouter(tags=["praesentation"])
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_SLIDE_ID = re.compile(r"^s\d+$")


@router.get("/praesentation/{job_uuid}")
async def get_praesentation(job_uuid: str, current_user: dict = Depends(get_current_user),
                            locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    outline = store.load_outline(user_id, job_uuid)
    slides = store.load_slides(user_id, job_uuid)
    progress = json.loads(job["progress"]) if job.get("progress") else None
    return {
        "job_uuid": job_uuid,
        "status": job["status"],
        "progress": progress,
        "error": job.get("error_message"),
        "params": params.model_dump() if params else None,
        "outline": outline.model_dump() if outline else None,
        "slides": [s.model_dump() for s in slides],
        "previews": [s.id for s in slides if store.has_preview(user_id, job_uuid, s.id)],
        "missing_images": [s.id for s in slides
                           if any(not store.has_image(user_id, job_uuid, s.id, k) for k in range(len(s.images)))
                           or (s.body is not None and s.body.kind == "image"
                               and not store.has_image(user_id, job_uuid, s.id, "body"))],
        "has_deck": store.has_deck(user_id, job_uuid),
    }


@router.get("/praesentation/{job_uuid}/preview/{slide_id}.png")
async def get_preview(job_uuid: str, slide_id: str, current_user: dict = Depends(get_current_user),
                      locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    if not _SLIDE_ID.match(slide_id):
        raise HTTPException(status_code=404)
    png = store.get_preview(job["user_id"], job_uuid, slide_id)
    if not png:
        raise HTTPException(status_code=404)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/praesentation/{job_uuid}/download")
async def download(job_uuid: str, current_user: dict = Depends(get_current_user),
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
        "Content-Disposition": f'attachment; filename="{name}.pptx"',
    })
