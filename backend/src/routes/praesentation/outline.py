"""The outline step: read, save, suggest one row anew, and release the slides."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.features.praesentation import gliederung, store, vorlage
from src.features.praesentation.schemas import FOLIEN_GRENZEN, Outline
from src.limits import PRAESENTATION_SLIDE_CONTEXT_CHARS
from src.i18n import get_locale, t
from src.limits import PRAESENTATION_MAX_SLIDES
from src.routes.praesentation._shared import (
    RegenRequest, llm_antwort, nicht_beschaeftigt, own_job, progress_final, verlauf,
)
from src.tasks.podcast_tasks._shared import clear_cancel
from src.tasks.praesentation_tasks import run_praesentation_build

router = APIRouter(tags=["praesentation"])


@router.put("/praesentation/{job_uuid}/outline")
async def save_outline(job_uuid: str, body: Outline, current_user: dict = Depends(get_current_user),
                       locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    nicht_beschaeftigt(job, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    analyse = store.load_template_meta(user_id, job_uuid)
    if not params or analyse is None:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    # Once slides exist the outline follows the built deck, so the floor drops and only the hard cap applies.
    hat_folien = bool(store.load_slides(user_id, job_uuid))
    bounds = (1, PRAESENTATION_MAX_SLIDES) if hat_folien else FOLIEN_GRENZEN
    lo, hi = bounds
    if len(body.rows) > hi:
        raise HTTPException(status_code=422, detail=t("praesentation.tooManySlides", locale, max=hi))
    try:
        outline = gliederung.pruefe(body, vorlage.waehlbare_rollen(analyse), bounds)
    except gliederung.Unusable as e:
        raise HTTPException(status_code=422, detail=t("praesentation.tooFewSlides", locale, min=lo)) from e
    store.save_user_outline(user_id, job_uuid, outline)
    return outline.model_dump()


@router.post("/praesentation/{job_uuid}/outline/{row_id}/regen")
async def regen_row(job_uuid: str, row_id: str, body: RegenRequest,
                    current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Returns the new title and gist, saving stays the caller's job."""
    job = own_job(job_uuid, current_user, locale)
    nicht_beschaeftigt(job, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    outline = store.load_outline(user_id, job_uuid)
    row = next((r for r in (outline.rows if outline else []) if r.id == row_id), None)
    if not params or row is None:
        raise HTTPException(status_code=404, detail=t("praesentation.rowNotFound", locale))
    from src.services import sources as quellen
    from src.services.text_map import Karte

    quellenliste = quellen.load_sources(user_id, job_uuid)
    # The row's own passages when it has them, else the start of the material.
    quelle = (Karte(quellenliste).passagen(row.stellen, budget=PRAESENTATION_SLIDE_CONTEXT_CHARS)
              if row.stellen else quellen.as_block(quellenliste)[:PRAESENTATION_SLIDE_CONTEXT_CHARS])
    try:
        titel, gist = gliederung.parse_row(llm_antwort(gliederung.regen_messages(row, outline, params, verlauf(body), quelle),
                                                        params.llm_provider_id))
    except Exception as e:  # noqa: BLE001 - the provider is the only source of failure here
        logger.warning("Präsentation: Zeile neu vorschlagen gescheitert: {}", e)
        raise HTTPException(status_code=502, detail=t("praesentation.regenFailed", locale)) from e
    return {"id": row_id, "title": titel, "gist": gist}


@router.post("/praesentation/{job_uuid}/build")
async def start_build(job_uuid: str, current_user: dict = Depends(get_current_user),
                      locale: str = Depends(get_locale)):
    job = own_job(job_uuid, current_user, locale)
    nicht_beschaeftigt(job, locale)
    user_id = job["user_id"]
    if store.load_outline(user_id, job_uuid) is None:
        raise HTTPException(status_code=422, detail=t("praesentation.tooFewSlides", locale, min=1))
    clear_cancel(job_uuid)
    db.reset_attempts(job_uuid)
    # Only a run that was parked mid-finalize keeps the intent, a finished deck starts over as a draft.
    final = progress_final(job) if job["status"] in ("waiting_retry", "paused", "failed") else False
    db.update_job_status(job_uuid, "pending", progress={"step": "texte", "final": final})
    task = run_praesentation_build.apply_async(args=[job_uuid, user_id, locale, 1, 0, None, final])
    db.set_job_celery_task_id(job_uuid, task.id)
    return {"job_uuid": job_uuid}
