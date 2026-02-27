"""Job status and download endpoints for async Celery tasks."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_current_user
from src.storage import delete_file, load_result_json

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


@router.get("/check/{tool_group}")
async def check_job_limit(
    tool_group: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if user can start a new job: active job exists? Storage limit reached?"""
    user_id = current_user.get("user_id", 0)

    _TOOL_GROUP_TOOLS = {
        "screencast": ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"],
        "tts": ["tts"],
        "video_dubbing": ["video_dubbing"],
    }

    tools = _TOOL_GROUP_TOOLS.get(tool_group, [])
    has_active = db.has_active_job_for_tool(user_id, tools) if tools else False

    # Check storage limit for result group
    from src.database import TOOL_RESULT_GROUP, MAX_RESULT_FILES
    result_group = {
        "screencast": "video",
        "tts": "tts",
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
):
    """Return the most recent jobs for the current user (default 20, max 200)."""
    user_id = current_user.get("user_id", 0)
    jobs = db.get_jobs_by_user(user_id, limit=limit)
    result = []
    for job in jobs:
        has_download = (
            job["status"] == "success"
            and job["result_path"]
            and Path(job["result_path"]).exists()
        )
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
        })
    return {"jobs": result}


@router.delete("/{job_uuid}")
async def cancel_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Cancel and delete a job. Revokes the Celery task if still running."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    # Revoke the Celery task (terminate=True sends SIGTERM to the worker process)
    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    # Delete files and DB record
    deleted = db.delete_job(job_uuid)
    if deleted:
        for path in (deleted.get("input_path"), deleted.get("result_path")):
            if path:
                delete_file(path)

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

    if job["status"] == "success" and job["result_path"]:
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
            meta_path = result_path.with_suffix(".meta.json")
            if meta_path.exists():
                try:
                    import json
                    response["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

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

    result_path = Path(job["result_path"])
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht mehr vorhanden (abgelaufen)")

    data = result_path.read_bytes()
    ext = result_path.suffix.lower()
    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
    filename = job["result_filename"] or result_path.name

    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
