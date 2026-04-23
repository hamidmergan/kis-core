"""Render-Endpoints: Pre-Render (Background) + finaler MP4-Render-Job."""

import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.storage import clear_tts_audio_cache, delete_job_folder, job_file_exists, save_job_file
from src.utils.file_validation import MAX_SCREENCAST_SLIDES, SCREENCAST_MAX_CHARS

from src.routes.screencast._models import PrerenderRequest, RenderRequest
from src.routes.screencast._shared import prerender_images_task

router = APIRouter(tags=["screencast"])


@router.post("/screencast/prerender-images")
async def prerender_images(body: PrerenderRequest, background_tasks: BackgroundTasks):
    """Start background pre-rendering of slide images at 300 DPI.

    Call this after the user confirms scripts so images are ready when /render is called.
    Fire-and-forget: always returns immediately.
    """
    if not re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige job UUID")
    background_tasks.add_task(prerender_images_task, body.translate_job_uuid)
    logger.info("Pre-render started for job={}", body.translate_job_uuid)
    return {"status": "started"}


@router.post("/screencast/render")
async def screencast_render(
    body: RenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Queue render phase on the existing translate job (single-folder workflow)."""
    if not body.scripts:
        raise HTTPException(status_code=400, detail="Keine Skripte übergeben")

    if len(body.scripts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(body.scripts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    total_chars = sum(len(s) for s in body.scripts)
    if total_chars > SCREENCAST_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Das Skript ist zu lang ({total_chars:,} Zeichen). Maximum: {SCREENCAST_MAX_CHARS:,} Zeichen.",
        )

    user_id = current_user.get("user_id", 0)

    # Validate translate job ownership + status
    translate_job = db.get_job(body.translate_job_uuid)
    if not translate_job:
        raise HTTPException(status_code=404, detail="Translate-Job nicht gefunden")
    if translate_job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
    if translate_job["status"] not in ("awaiting_user", "failed", "success"):
        raise HTTPException(status_code=409, detail="Job ist nicht bereit zum Rendern")
    if not job_file_exists(body.translate_job_uuid, "translated.pptx"):
        delete_job_folder(body.translate_job_uuid)
        db.delete_job(body.translate_job_uuid)
        raise HTTPException(status_code=404, detail="Job-Dateien nicht mehr vorhanden. Bitte neue Übersetzung starten.")

    # If re-rendering a previously completed job, clear stale TTS audio so the
    # crash-recovery mechanism doesn't reuse old audio for the new scripts.
    if translate_job["status"] == "success":
        clear_tts_audio_cache(body.translate_job_uuid)
        logger.info("Re-render: cleared TTS audio cache for job={}", body.translate_job_uuid)

    # Save scripts and render params for queue dispatch (used by dispatch_next)
    save_job_file(body.translate_job_uuid, "render_scripts.json", json.dumps(body.scripts, ensure_ascii=False).encode())
    save_job_file(body.translate_job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "render",
        "voice_id": body.voice_id,
        "speed": body.speed,
        "slide_pause": body.slide_pause,
        "dpi": body.dpi,
        "provider": body.provider,
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
        raise HTTPException(status_code=409, detail="Dieser Job wird bereits verarbeitet.")

    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)

    logger.info("Screencast render queued: translate_job={}", body.translate_job_uuid)
    return {"job_uuid": body.translate_job_uuid}
