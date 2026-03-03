"""Job status and download endpoints for async Celery tasks."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_current_user
from src.storage import USE_S3, delete_job_folder, file_exists, get_file, get_job_file, load_result_json, load_result_meta

router = APIRouter(prefix="/jobs", tags=["jobs"])

_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".tex": "application/x-tex",
    ".txt": "text/plain",
    ".html": "text/html",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}


_TOOL_LABELS = {
    "screencast_demo_render": "Demo-Screencast",
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast-Übersetzung",
    "screencast_auto": "Screencast (Auto)",
    "tts": "Text-to-Speech",
    "video_dubbing": "Video-Dubbing",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
    "script": "Skript-Erstellung",
    "summary": "Zusammenfassung",
}


def _tools_matching_query(q: str) -> list[str]:
    """Return tool keys whose label contains q (case-insensitive, umlaut-safe)."""
    q_lower = q.lower()
    return [k for k, label in _TOOL_LABELS.items() if q_lower in label.lower()]


@router.get("/check/{tool_group}")
async def check_job_limit(
    tool_group: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if user can start a new job: active job exists? Storage limit reached?"""
    user_id = current_user.get("user_id", 0)

    _TOOL_GROUP_TOOLS = {
        "screencast": ["screencast_translate", "screencast_auto", "screencast_demo_render"],
        "tts": ["tts"],
        "video_dubbing": ["video_dubbing"],
    }

    tools = _TOOL_GROUP_TOOLS.get(tool_group, [])
    has_active = db.has_active_job_for_tool(user_id, tools) if tools else False

    # Check storage limit for result group
    from src.database import TOOL_RESULT_GROUP, MAX_RESULT_FILES
    result_group = {
        "screencast": "video",
        "tts": "general",
        "video_dubbing": "video",
    }.get(tool_group)

    at_storage_limit = False
    evict_filename = None

    if result_group:
        existing = db.get_results_for_tool_group(user_id, result_group)
        limit = MAX_RESULT_FILES.get(result_group, 5)
        if len(existing) >= limit:
            at_storage_limit = True
            evict_filename = existing[0].get("original_filename") or existing[0].get("result_filename")

    return {
        "has_active_job": has_active,
        "at_storage_limit": at_storage_limit,
        "evict_filename": evict_filename,
    }


@router.get("/my")
async def get_my_jobs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    hide_expired: bool = Query(default=True),
):
    """Return jobs for the current user with optional search and date filters."""
    user_id = current_user.get("user_id", 0)
    extra_tools = _tools_matching_query(q) if q else None
    jobs, total = db.get_jobs_by_user(user_id, limit=limit, offset=offset, q=q, date_from=date_from, date_to=date_to, extra_tools=extra_tools, hide_expired=hide_expired)
    result = []
    for job in jobs:
        has_download = (
            job["status"] == "success"
            and bool(job["result_path"])
            and file_exists(job["result_path"])
        )
        created_at = job["created_at"] or ""
        date_part = created_at[:10]
        time_part = created_at[11:19].replace(":", "-") if len(created_at) >= 19 else ""
        folder_name = f"{date_part}_{time_part}_{job['job_uuid']}" if date_part and time_part else job["job_uuid"]
        result.append({
            "job_uuid": job["job_uuid"],
            "tool": job["tool"],
            "tool_label": _TOOL_LABELS.get(job["tool"], job["tool"]),
            "original_filename": job["original_filename"],
            "status": job["status"],
            "error": job["error_message"],
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"],
            "expires_at": job["expires_at"],
            "has_download": has_download,
            "result_filename": job["result_filename"],
            "folder_name": folder_name,
        })

    return {"jobs": result, "total": total}


@router.post("/{job_uuid}/retry")
async def retry_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-queue a failed TTS job. Resumes from already-saved chunks — no double payment."""
    import json
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["tool"] not in ("tts", "screencast_translate", "screencast_render", "screencast_demo_render"):
        raise HTTPException(status_code=400, detail="Retry nur für TTS- und Screencast-Jobs verfügbar")
    if job["status"] == "success":
        raise HTTPException(status_code=409, detail="Job bereits erfolgreich abgeschlossen")
    if job["status"] in ("running", "pending"):
        raise HTTPException(status_code=409, detail="Job läuft bereits")
    progress = json.loads(job["progress"] or "{}")

    # Load and validate all params BEFORE claiming the job atomically
    if job["tool"] == "tts":
        if not job["input_path"]:
            raise HTTPException(status_code=400, detail="Eingabedatei nicht mehr vorhanden (abgelaufen)")
        params = progress.get("tts_params")
        if not params:
            raise HTTPException(status_code=400, detail="Job-Parameter nicht gespeichert — bitte neuen Job starten")

    elif job["tool"] in ("screencast_translate", "screencast_render"):
        try:
            render_params = json.loads(get_job_file(job_uuid, "render_params.json"))
            scripts = json.loads(get_job_file(job_uuid, "render_scripts.json"))
        except Exception:
            raise HTTPException(status_code=400, detail="Render-Parameter nicht mehr vorhanden — bitte neuen Screencast starten")

    else:  # screencast_demo_render
        try:
            demo_params = json.loads(get_job_file(job_uuid, "demo_params.json"))
        except Exception:
            raise HTTPException(status_code=400, detail="Demo-Parameter nicht mehr vorhanden (abgelaufen)")

    # Atomically claim the job — blocks parallel retries
    if not db.claim_job_for_retry(job_uuid):
        raise HTTPException(status_code=409, detail="Job läuft bereits (parallel gestartet)")

    if job["tool"] == "tts":
        from src.tasks.tts_tasks import run_tts
        task = run_tts.apply_async(args=[
            job_uuid,
            job["input_path"],
            job["original_filename"],
            params["voice_id"],
            params["speed"],
            params["stability"],
            params["similarity_boost"],
            params["style"],
            params["use_speaker_boost"],
            params["pause_preset"],
        ])

    elif job["tool"] in ("screencast_translate", "screencast_render"):
        from src.tasks.screencast_tasks import run_screencast_render
        task = run_screencast_render.apply_async(args=[
            job_uuid,
            scripts,
            render_params["voice_id"],
            render_params["speed"],
            render_params["slide_pause"],
            render_params["embed_subtitles"],
            job["original_filename"],
            render_params["dpi"],
        ])

    else:  # screencast_demo_render
        from src.tasks.screencast_tasks import run_screencast_demo_render
        task = run_screencast_demo_render.apply_async(args=[
            job_uuid,
            demo_params["dpi"],
        ])

    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("{} job {} re-queued via retry by user {}", job["tool"], job_uuid, current_user.get("user_id"))
    return {"ok": True}


@router.delete("/{job_uuid}")
async def cancel_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Cancel and delete a job. Revokes the Celery task if still running."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")

    # Revoke the Celery task (terminate=True sends SIGTERM to the worker process)
    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    # Delete all job files first — delete_job_folder reads created_at from DB
    # to resolve the folder name (YYYY-MM-DD_HH-MM-SS_{uuid}). Deleting DB first
    # would cause the lookup to fail and miss the real MinIO folder.
    delete_job_folder(job_uuid)
    db.delete_job(job_uuid)

    logger.info("Job cancelled: {}", job_uuid)
    return {"ok": True}


@router.get("/{job_uuid}")
async def get_job_status(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll job status. Returns progress while running, result when done."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    response: dict = {
        "job_uuid": job_uuid,
        "status": job["status"],
        "tool": job["tool"],
        "progress": None,
        "error": job["error_message"],
        "filename": job["result_filename"],
        "download_url": None,
        "result": None,
        "meta": None,
    }

    if job["progress"]:
        import json
        try:
            response["progress"] = json.loads(job["progress"])
        except Exception:
            pass

    if job["status"] in ("success", "awaiting_user") and job["result_path"]:
        result_path = Path(job["result_path"])

        if result_path.suffix == ".json":
            # Inline JSON result (e.g. screencast/translate)
            try:
                response["result"] = load_result_json(job["result_path"])
            except Exception as e:
                logger.error("Failed to load result JSON for {}: {}", job_uuid, e)
                raise HTTPException(status_code=500, detail="Ergebnis konnte nicht geladen werden")
        else:
            # Binary result (MP4, MP3) — provide download URL
            response["download_url"] = f"/jobs/{job_uuid}/download"

            # For render jobs: load subtitle + audio metadata
            meta = load_result_meta(job_uuid)
            if meta is not None:
                response["meta"] = meta

    return response


@router.get("/{job_uuid}/download")
async def download_job_result(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the binary result file (MP4 or MP3) for a completed job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["status"] != "success":
        raise HTTPException(status_code=404, detail="Job noch nicht abgeschlossen")
    if not job["result_path"]:
        raise HTTPException(status_code=404, detail="Kein Download für diesen Job")

    result_path_str = job["result_path"]
    try:
        data = get_file(result_path_str)
    except Exception:
        raise HTTPException(status_code=404, detail="Datei nicht mehr vorhanden (abgelaufen)")

    ext = Path(result_path_str).suffix.lower()
    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
    filename = job["result_filename"] or Path(result_path_str).name

    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_uuid}/pptx")
async def download_job_pptx(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the translated PPTX for a screencast render job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if not job["result_path"]:
        raise HTTPException(status_code=404, detail="PPTX nicht mehr vorhanden (abgelaufen)")

    # Derive PPTX path from stored result_path — avoids re-computing the job folder name.
    # Both translated.pptx and the result file (MP4/JSON) live in the same job folder.
    pptx_path = str(Path(job["result_path"]).parent / "translated.pptx")
    try:
        data = get_file(pptx_path)
    except Exception as e:
        logger.error("PPTX download failed for job {} (path: {}): {}", job_uuid, pptx_path, e)
        raise HTTPException(status_code=404, detail="PPTX nicht mehr vorhanden (abgelaufen)")

    stem = Path(job["original_filename"]).stem if job["original_filename"] else "screencast"

    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{stem}_praesentation.pptx"',
        },
    )
