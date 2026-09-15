"""Render-Endpoints: Pre-Render (Background) + finaler MP4-Render-Job."""

import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.storage import (
    clear_render_cache,
    delete_job_folder,
    get_job_file,
    job_file_exists,
    load_result_meta,
    save_job_file,
    save_result_meta,
)
from src.utils.file_validation import SCREENCAST_MAX_CHARS
from src.services.tool_limits import max_screencast_slides

from src.routes.screencast._models import PrerenderRequest, RenderRequest


def _merke_zielsprache(user_id: int, job_uuid: str, target_lang: str) -> None:
    """The voicing reads the language here later, on a re-render too."""
    if not target_lang:
        return
    save_result_meta(user_id, job_uuid, {**(load_result_meta(user_id, job_uuid) or {}),
                                         "target_lang": target_lang})


def _vorrat_passt_nicht(user_id: int, job_uuid: str, body) -> bool:
    """Voice, provider or language changed? Then the pooled audio is the wrong one."""
    try:
        alt = json.loads(get_job_file(user_id, job_uuid, "queue_params.json"))
    except Exception:
        return False
    alt_sprache = (load_result_meta(user_id, job_uuid) or {}).get("target_lang", "")
    return (
        alt.get("voice_id") != body.voice_id
        or int(alt.get("provider_id", 0) or 0) != int(body.provider_id or 0)
        or alt_sprache != body.target_lang
    )


from src.routes.screencast._shared import prerender_images_task

router = APIRouter(tags=["screencast: render"])


@router.post("/screencast/prerender-images")
async def prerender_images(
    body: PrerenderRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Starts pre-rendering the slide images and returns right away."""
    if not re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    # Only the owner may pre-render, missing and foreign give the same answer.
    job = db.get_job(body.translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("screencast.translateJobNotFound", locale))
    background_tasks.add_task(prerender_images_task, body.translate_job_uuid, body.dpi)
    logger.info("Pre-render started for job={} at {} DPI", body.translate_job_uuid, body.dpi)
    return {"status": "started"}


@router.post("/screencast/render")
def screencast_render(
    body: RenderRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue render phase on the existing translate job (single-folder workflow)."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail=t("screencast.noScripts", locale))

    folien_grenze = max_screencast_slides()
    if len(body.scripts) > folien_grenze:
        raise HTTPException(
            status_code=400,
            detail=t(
                "screencast.tooManySlides",
                locale,
                count=len(body.scripts),
                max=folien_grenze,
            ),
        )

    gueltig = range(len(body.scripts))
    if body.video_folien is not None:
        if not body.video_folien:
            raise HTTPException(status_code=400, detail=t("screencast.keineFolieGewaehlt", locale))
        if any(i not in gueltig for i in body.video_folien):
            raise HTTPException(status_code=400, detail=t("screencast.folieUnbekannt", locale))
    if any(i not in gueltig for i in body.neu_vertonen):
        raise HTTPException(status_code=400, detail=t("screencast.folieUnbekannt", locale))

    dabei = set(body.video_folien) if body.video_folien is not None else set(gueltig)
    total_chars = sum(len(s) for i, s in enumerate(body.scripts) if i in dabei)
    if total_chars > SCREENCAST_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=t(
                "screencast.scriptTooLong",
                locale,
                chars=f"{total_chars:,}",
                maxChars=f"{SCREENCAST_MAX_CHARS:,}",
            ),
        )

    user_id = current_user.get("user_id", 0)

    # Validate translate job ownership + status
    translate_job = db.get_job(body.translate_job_uuid)
    if not translate_job:
        raise HTTPException(status_code=404, detail=t("screencast.translateJobNotFound", locale))
    if translate_job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))
    if translate_job["status"] not in ("awaiting_user", "failed", "success", "paused"):
        raise HTTPException(status_code=409, detail=t("screencast.notReadyForRender", locale))
    if not job_file_exists(user_id, body.translate_job_uuid, "translated.pptx"):
        delete_job_folder(user_id, body.translate_job_uuid)
        db.delete_job(body.translate_job_uuid)
        raise HTTPException(status_code=404, detail=t("screencast.jobFilesGone", locale))

    # Throw the pool away when it no longer fits.
    if translate_job["status"] == "success" or _vorrat_passt_nicht(user_id, body.translate_job_uuid, body):
        clear_render_cache(user_id, body.translate_job_uuid)
        logger.info("Vorrat geleert fuer job={}", body.translate_job_uuid)

    _merke_zielsprache(user_id, body.translate_job_uuid, body.target_lang)

    # Save scripts and render params for queue dispatch (used by dispatch_next)
    save_job_file(user_id, body.translate_job_uuid, "render_scripts.json", json.dumps(body.scripts, ensure_ascii=False).encode())
    save_job_file(user_id, body.translate_job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "render",
        "voice_id": body.voice_id,
        "speed": body.speed,
        "slide_pause": body.slide_pause,
        "dpi": body.dpi,
        "provider_id": body.provider_id,
        "voice_label": body.voice_label,
        "is_admin": is_admin_user(current_user),
        "subtitles": body.subtitles,
        "video_folien": body.video_folien,
        "neu_vertonen": body.neu_vertonen,
    }).encode())

    # Atomically transition to queued (prevents duplicate submissions from multiple tabs)
    transitioned = db.transition_job_to_queued(
        body.translate_job_uuid,
        user_id,
        from_statuses=("awaiting_user", "failed", "success", "paused"),
    )
    if not transitioned:
        raise HTTPException(status_code=409, detail=t("screencast.alreadyProcessing", locale))
    db.reset_attempts(body.translate_job_uuid)

    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)

    logger.info("Screencast render queued: translate_job={}", body.translate_job_uuid)
    return {"job_uuid": body.translate_job_uuid}
