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
from src.limits import MAX_QUEUED_SCREENCAST_JOBS, BUNDLE_INCLUDE_AUDIO, BUNDLE_INCLUDE_IMAGES
from src.storage import USE_S3, delete_job_folder, file_exists, get_file, get_job_file, job_file_exists, load_result_json, load_result_meta, save_job_file, _job_folder_name

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
    "tts": "Text in Sprache",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
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
        "screencast": ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"],
        "tts": ["tts"],
    }

    _TOOL_GROUP_LIMITS = {
        "screencast": MAX_QUEUED_SCREENCAST_JOBS,
    }

    tools = _TOOL_GROUP_TOOLS.get(tool_group, [])
    max_jobs = _TOOL_GROUP_LIMITS.get(tool_group, 1)
    has_active = db.count_all_jobs_for_tool(user_id, tools) >= max_jobs if tools else False

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
    return (val.isoformat() + "Z") if hasattr(val, "isoformat") else val


_META_TOOLS = {"screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"}


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
        is_generating_scripts = False
        tool = job["tool"]
        if tool in ("tts", "screencast_auto", "screencast_render", "screencast_translate",
                    "screencast_demo_render"):
            try:
                progress = json_lib.loads(job["progress"] or "{}")
                if tool == "tts":
                    tts_params = progress.get("tts_params", {})
                else:
                    tts_params = {k: progress[k] for k in ("voice_id", "voice_label", "provider") if k in progress}
                if tool in ("screencast_translate", "screencast_demo_render"):
                    is_generating_scripts = bool(progress.get("generating_scripts"))
            except Exception:
                pass

        meta = None
        if job["status"] == "success" and tool in _META_TOOLS:
            meta = load_result_meta(job["job_uuid"])

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
            "render_queued_at": _dt(job["render_queued_at"]),
            "expires_at": _dt(job["expires_at"]),
            "has_download": has_download,
            "result_filename": job["result_filename"],
            "folder_name": folder_name,
            "tts_params": tts_params or None,
            "is_generating_scripts": is_generating_scripts,
            "meta": meta,
        })
    return result


_TOOL_FILTER_GROUPS: dict[str, list[str]] = {
    "screencast": ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"],
    "image": ["image_generate", "image_edit", "image_analyze"],
}


def _expand_tool_filter(tool_filter: str) -> list[str] | None:
    if not tool_filter:
        return None
    return _TOOL_FILTER_GROUPS.get(tool_filter, [tool_filter])


@router.get("/my")
async def get_my_jobs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    tool_filter: str = Query(default=""),
):
    """Return jobs for the current user with optional search and date filters."""
    user_id = current_user.get("user_id", 0)
    extra_tools = _tools_matching_query(q) if q else None
    tool_filter_list = _expand_tool_filter(tool_filter)
    jobs, total = db.get_jobs_by_user(
        user_id, limit=limit, offset=offset, q=q,
        date_from=date_from, date_to=date_to,
        extra_tools=extra_tools, tool_filter=tool_filter_list,
    )
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

    _SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_auto", "screencast_demo_render"]

    if job["tool"] == "tts":
        # Atomically claim the job — blocks parallel retries
        if not db.claim_job_for_retry(job_uuid):
            raise HTTPException(status_code=409, detail="Job läuft bereits (parallel gestartet)")

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
        try:
            import redis as _redis
            _r = _redis.from_url("redis://kis-redis:6379/0")
            _r.delete(f"job:cancel:{job_uuid}")
        except Exception as e:
            logger.warning("Could not clear cancel flag in Redis: {}", e)
        db.set_job_celery_task_id(job_uuid, task.id)

    elif job["tool"] in ("screencast_translate", "screencast_render"):
        save_job_file(job_uuid, "queue_params.json", json.dumps({
            "dispatch_as": "render",
            "voice_id": render_params["voice_id"],
            "speed": render_params["speed"],
            "slide_pause": render_params["slide_pause"],
            "dpi": render_params["dpi"],
            "provider": render_params.get("provider", "elevenlabs"),
            "voice_label": render_params.get("voice_label", ""),
            "is_admin": render_params.get("is_admin", False),
        }).encode())
        if not db.transition_job_to_queued(job_uuid, job["user_id"], from_statuses=("failed",)):
            raise HTTPException(status_code=409, detail="Job läuft bereits (parallel gestartet)")
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])

    else:  # screencast_demo_render
        save_job_file(job_uuid, "queue_params.json", json.dumps({
            "dispatch_as": "demo_render",
            "dpi": demo_params["dpi"],
        }).encode())
        if not db.transition_job_to_queued(job_uuid, job["user_id"], from_statuses=("failed",)):
            raise HTTPException(status_code=409, detail="Job läuft bereits (parallel gestartet)")
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])

    logger.info("{} job {} re-queued via retry by user {}", job["tool"], job_uuid, current_user.get("user_id"))
    return {"ok": True}


@router.post("/{job_uuid}/cancel")
async def cancel_job_render(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Stop a running render without deleting job data. Sets status back to awaiting_user."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")

    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    # Set a Redis cancellation flag so the worker stops at the next checkpoint
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        _r.setex(f"job:cancel:{job_uuid}", 600, "1")  # 10 min TTL
        logger.info("Cancel flag set in Redis for job={}", job_uuid)
    except Exception as e:
        logger.warning("Could not set cancel flag in Redis: {}", e)

    db.reset_job_to_awaiting(job_uuid)
    try:
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])
    except Exception as e:
        logger.warning("Could not dispatch next queued job after soft-cancel: {}", e)
    logger.info("Job render soft-cancelled: {}", job_uuid)
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

    # Set Redis cancellation flag so the worker stops at the next checkpoint
    # (same mechanism as POST /cancel). Without this, _assert_not_cancelled()
    # never triggers and the worker keeps running despite the revoke.
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        _r.setex(f"job:cancel:{job_uuid}", 600, "1")
    except Exception as e:
        logger.warning("Could not set cancel flag in Redis: {}", e)

    # Delete all job files first — delete_job_folder reads created_at from DB
    # to resolve the folder name (YYYY-MM-DD_HH-MM-SS_{uuid}). Deleting DB first
    # would cause the lookup to fail and miss the real MinIO folder.
    delete_job_folder(job_uuid)
    db.delete_job(job_uuid)

    # Notify SSE clients that job list changed (job was removed)
    # Must happen after delete but we still have user_id from the job dict above.
    try:
        import redis as _redis_notify
        _rn = _redis_notify.from_url("redis://kis-redis:6379/0", socket_connect_timeout=1, socket_timeout=1)
        _rn.publish(f"jobs:{job['user_id']}", "update")
        _rn.close()
    except Exception as e:
        logger.warning("Could not notify SSE after job delete: {}", e)

    # Clean up pre-rendered slide image cache (screencast jobs only, ignored for others)
    try:
        import shutil as _shutil
        from src.services.screencast import IMAGE_TMP_DIR
        _shutil.rmtree(IMAGE_TMP_DIR / job_uuid, ignore_errors=True)
    except Exception:
        pass

    # If a screencast job was cancelled, dispatch the next queued job for this user
    _SCREENCAST_TOOLS = {"screencast_translate", "screencast_auto", "screencast_render", "screencast_demo_render"}
    if job.get("tool") in _SCREENCAST_TOOLS:
        try:
            from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
            dispatch_next_screencast_job_for_user(job["user_id"])
        except Exception as e:
            logger.warning("Could not dispatch next queued screencast job after cancel: {}", e)

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
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
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


class _ZipStreamWriter:
    """File-like object that collects written bytes into chunks for streaming."""

    def __init__(self):
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self._buf.write(data)

    def flush(self):
        pass

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf.seek(offset, whence)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def close(self):
        pass


def _streaming_zip_bundle(job_uuid: str, folder_name: str, audio_count: int):
    """Generator that yields ZIP data file-by-file without buffering everything first."""

    # Collect (arcname, data) pairs — yield each file's ZIP contribution immediately
    stream = _ZipStreamWriter()
    zf = zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED)

    def _add_and_yield(arcname: str, data: bytes):
        pos_before = stream.tell()
        zf.writestr(arcname, data)
        pos_after = stream.tell()
        stream.seek(pos_before)
        chunk = stream.read(pos_after - pos_before)
        return chunk

    # MP4
    try:
        mp4_data = get_job_file(job_uuid, "output.mp4")
        yield _add_and_yield(f"{folder_name}.mp4", mp4_data)
        del mp4_data
    except Exception:
        pass

    # Slide audios
    if BUNDLE_INCLUDE_AUDIO:
        for i in range(audio_count):
            try:
                audio_data = get_job_file(job_uuid, f"audio/slide_{i:03d}.mp3")
                yield _add_and_yield(f"Audios/slide_{i + 1:03d}.mp3", audio_data)
            except Exception:
                pass

    # PPTX
    pptx_name = "corrected.pptx" if job_file_exists(job_uuid, "corrected.pptx") else "translated.pptx"
    try:
        pptx_data = get_job_file(job_uuid, pptx_name)
        yield _add_and_yield(f"{folder_name}.pptx", pptx_data)
    except Exception:
        pass

    # Script
    for script_file in ("accepted_scripts.json", "user_scripts.json", "scripts.txt"):
        try:
            script_data = get_job_file(job_uuid, script_file)
            yield _add_and_yield(script_file, script_data)
            break
        except Exception:
            continue

    # Finalize ZIP (central directory)
    pos_before = stream.tell()
    zf.close()
    pos_after = stream.tell()
    stream.seek(pos_before)
    yield stream.read(pos_after - pos_before)


@router.get("/{job_uuid}/bundle")
async def download_job_bundle(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a ZIP bundle containing MP4, slide audios, PPTX and script for a screencast job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.get("user_id") != current_user.get("user_id"):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    folder_name = _job_folder_name(job_uuid)
    meta = load_result_meta(job_uuid) or {}
    audio_count = int(meta.get("audio_count", 0))
    zip_filename = f"{folder_name}.zip"

    return StreamingResponse(
        _streaming_zip_bundle(job_uuid, folder_name, audio_count),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
