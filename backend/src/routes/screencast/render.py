"""Render-Endpoints: Pre-Render (Background) + finaler MP4-Render-Job."""

import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.storage import clear_render_cache, delete_job_folder, job_file_exists, save_job_file
from src.utils.file_validation import MAX_SCREENCAST_SLIDES, SCREENCAST_MAX_CHARS

from src.routes.screencast._models import PrerenderRequest, RenderRequest
from src.routes.screencast._shared import prerender_images_task

router = APIRouter(tags=["screencast: render"])


@router.post("/screencast/prerender-images")
async def prerender_images(
    body: PrerenderRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Start background pre-rendering of slide images at 300 DPI.

    Call this after the user confirms scripts so images are ready when /render is called.
    Fire-and-forget: always returns immediately.
    """
    if not re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    # Ownership check: only the job owner may trigger pre-rendering. Same status
    # for missing and not-owned so job existence cannot be probed.
    job = db.get_job(body.translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("screencast.translateJobNotFound", locale))
    background_tasks.add_task(prerender_images_task, body.translate_job_uuid)
    logger.info("Pre-render started for job={}", body.translate_job_uuid)
    return {"status": "started"}


@router.post("/screencast/render")
async def screencast_render(
    body: RenderRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue render phase on the existing translate job (single-folder workflow)."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail=t("screencast.noScripts", locale))

    if len(body.scripts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=t(
                "screencast.tooManySlides",
                locale,
                count=len(body.scripts),
                max=MAX_SCREENCAST_SLIDES,
            ),
        )

    total_chars = sum(len(s) for s in body.scripts)
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
    if translate_job["status"] not in ("awaiting_user", "failed", "success"):
        raise HTTPException(status_code=409, detail=t("screencast.notReadyForRender", locale))
    if not job_file_exists(user_id, body.translate_job_uuid, "translated.pptx"):
        delete_job_folder(user_id, body.translate_job_uuid)
        db.delete_job(body.translate_job_uuid)
        raise HTTPException(status_code=404, detail=t("screencast.jobFilesGone", locale))

    # If re-rendering a previously completed job, clear stale TTS audio so the
    # crash-recovery mechanism doesn't reuse old audio for the new scripts.
    if translate_job["status"] == "success":
        clear_render_cache(user_id, body.translate_job_uuid)
        logger.info("Re-render: cleared render cache for job={}", body.translate_job_uuid)

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
    }).encode())

    # Atomically transition to queued (prevents duplicate submissions from multiple tabs)
    transitioned = db.transition_job_to_queued(
        body.translate_job_uuid,
        user_id,
        from_statuses=("awaiting_user", "failed", "success"),
    )
    if not transitioned:
        raise HTTPException(status_code=409, detail=t("screencast.alreadyProcessing", locale))

    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)

    logger.info("Screencast render queued: translate_job={}", body.translate_job_uuid)
    return {"job_uuid": body.translate_job_uuid}
