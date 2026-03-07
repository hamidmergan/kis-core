"""Job status and download endpoints for async Celery tasks."""

import base64
import io
import json as json_lib
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_current_user
from src.storage import USE_S3, delete_job_folder, file_exists, get_file, get_job_file, load_result_json, load_result_meta

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

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

    # Check storage limit
    from src.database import MAX_RESULT_FILES
    existing = db.get_all_results_for_user(user_id)
    at_storage_limit = len(existing) >= MAX_RESULT_FILES
    evict_filename = None
    if at_storage_limit:
        evict_filename = existing[0].get("original_filename") or existing[0].get("result_filename")

    return {
        "has_active_job": has_active,
        "at_storage_limit": at_storage_limit,
        "evict_filename": evict_filename,
    }


def _dt(val) -> str | None:
    """Convert datetime or string to ISO string, or return None."""
    if val is None:
        return None
    return val.isoformat() if hasattr(val, "isoformat") else val


def _format_job_rows(jobs: list[dict]) -> list[dict]:
    """Format raw DB job rows into the standard API response format."""
    result = []
    for job in jobs:
        has_download = (
            job["status"] == "success"
            and bool(job["result_path"])
            and file_exists(job["result_path"])
        )
        created_at_raw = job["created_at"]
        created_at = created_at_raw.isoformat() if hasattr(created_at_raw, "isoformat") else (created_at_raw or "")
        date_part = created_at[:10]
        time_part = created_at[11:19].replace(":", "-") if len(created_at) >= 19 else ""
        folder_name = f"{date_part}_{time_part}_{job['job_uuid']}" if date_part and time_part else job["job_uuid"]

        tts_params: dict = {}
        tool = job["tool"]
        if tool in ("tts", "screencast_auto", "screencast_render", "screencast_translate",
                    "screencast_demo_render"):
            try:
                progress = json_lib.loads(job["progress"] or "{}")
                if tool == "tts":
                    tts_params = progress.get("tts_params", {})
                else:
                    tts_params = {k: progress[k] for k in ("voice_id", "voice_label", "provider") if k in progress}
            except Exception:
                pass

        result.append({
            "job_uuid": job["job_uuid"],
            "tool": tool,
            "tool_label": _TOOL_LABELS.get(tool, tool),
            "original_filename": job["original_filename"],
            "status": job["status"],
            "error": job["error_message"],
            "created_at": _dt(job["created_at"]),
            "started_at": _dt(job["started_at"]),
            "completed_at": _dt(job["completed_at"]),
            "render_started_at": _dt(job["render_started_at"]),
            "expires_at": _dt(job["expires_at"]),
            "has_download": has_download,
            "result_filename": job["result_filename"],
            "folder_name": folder_name,
            "tts_params": tts_params or None,
        })
    return result


@router.get("/my")
async def get_my_jobs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
):
    """Return jobs for the current user with optional search and date filters."""
    user_id = current_user.get("user_id", 0)
    extra_tools = _tools_matching_query(q) if q else None
    jobs, total = db.get_jobs_by_user(user_id, limit=limit, offset=offset, q=q, date_from=date_from, date_to=date_to, extra_tools=extra_tools)
    return {"jobs": _format_job_rows(jobs), "total": total}


@router.get("/stream")
async def job_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """SSE endpoint: streams job list updates whenever a job status changes."""
    import redis.asyncio as aioredis

    user_id = current_user.get("user_id", 0)

    async def event_generator():
        # Send initial snapshot immediately on connect
        jobs, total = db.get_jobs_by_user(user_id, limit=20)
        yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs), 'total': total})}\n\n"

        r = aioredis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"jobs:{user_id}")
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg["type"] == "message":
                    jobs, total = db.get_jobs_by_user(user_id, limit=20)
                    yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs), 'total': total})}\n\n"
        finally:
            await pubsub.unsubscribe(f"jobs:{user_id}")
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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
            job["original_filename"] or "screencast.pptx",
            render_params["dpi"],
            render_params.get("provider", "elevenlabs"),
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

    # Multi-image JSON → ZIP (or single PNG direct)
    if ext == ".json" and job["tool"] == "image_generate":
        try:
            images_data = json_lib.loads(data)["images"]
        except Exception:
            raise HTTPException(status_code=500, detail="Bilddaten konnten nicht gelesen werden")

        if len(images_data) == 1:
            img_bytes = base64.b64decode(images_data[0]["b64_json"])
            png_filename = images_data[0].get("filename", "image.png")
            return StreamingResponse(
                iter([img_bytes]),
                media_type="image/png",
                headers={
                    "Content-Length": str(len(img_bytes)),
                    "Content-Disposition": f'attachment; filename="{png_filename}"',
                },
            )
        else:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for img in images_data:
                    img_bytes = base64.b64decode(img["b64_json"])
                    zf.writestr(img.get("filename", "image.png"), img_bytes)
            zip_bytes = buf.getvalue()
            base_name = (job["result_filename"] or "images").removesuffix(".json")
            zip_filename = f"{base_name}.zip"
            return StreamingResponse(
                iter([zip_bytes]),
                media_type="application/zip",
                headers={
                    "Content-Length": str(len(zip_bytes)),
                    "Content-Disposition": f'attachment; filename="{zip_filename}"',
                },
            )

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

    # Use get_job_file so the folder name (YYYY-MM-DD_HH-MM-SS_{uuid}) is resolved
    # correctly from the DB — works for both screencast_translate (has result_path)
    # and screencast_demo_render (result_path is NULL, but translated.pptx is in folder).
    from src.storage import get_job_file
    try:
        data = get_job_file(job_uuid, "translated.pptx")
    except Exception as e:
        logger.error("PPTX download failed for job {}: {}", job_uuid, e)
        raise HTTPException(status_code=404, detail="PPTX nicht mehr vorhanden (abgelaufen)")

    from src.services.translation import translate_output_filename
    pptx_filename = translate_output_filename(job["original_filename"] or "screencast.pptx", output_ext=".pptx")

    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{pptx_filename}"',
        },
    )
