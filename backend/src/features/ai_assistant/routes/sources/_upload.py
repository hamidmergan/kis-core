"""Source upload / retry / delete."""
import asyncio
import os
import tempfile
import time
import uuid

from src.security.rate_limit import check_upload_limit, record_upload
from src.utils.file_validation import validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

from ._shared import (
    Path, APIRouter, Depends, File, HTTPException, UploadFile, logger, db,
    get_current_user, get_locale, t,
    AIA_MAX_CONCURRENT_UPLOADS, AIA_SOURCE_MAX_PAGES, AIA_WORKSPACE_MAX_SOURCES,
    delete_aia_source_files,
    _convert_office_to_pdf_path, _mp4_faststart_path, _count_pages_path,
    _require_workspace_manage, _load_workspace_source, _save_source_file_path,
    _workspace_label,
    _ALLOWED_EXTENSIONS, _MAX_UPLOAD_BYTES,
)

router = APIRouter(tags=["ki-assistent: sources"])

# Global upload brake in Redis, as a sorted set with timestamps.
_UPLOAD_SET_KEY = "kis:uploads:inflight"
# How long a slot is valid at most, an orphan heals by itself afterwards.
_UPLOAD_STALE_SECONDS = 15 * 60

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")


def _redis():
    """Redis client with short timeouts, same pattern as rate_limit.py."""
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _max_concurrent_uploads() -> int:
    """How many uploads may pass through the heavy phase at once."""
    return AIA_MAX_CONCURRENT_UPLOADS


def _claim_upload_slot(limit: int) -> str | None:
    """Claims an upload slot, or None when full."""
    ticket = uuid.uuid4().hex
    now = time.time()
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.zremrangebyscore(_UPLOAD_SET_KEY, "-inf", now - _UPLOAD_STALE_SECONDS)
        pipe.zcard(_UPLOAD_SET_KEY)
        in_flight = pipe.execute()[1]
        if 0 < limit <= in_flight:
            return None
        r.zadd(_UPLOAD_SET_KEY, {ticket: now})
        return ticket
    except Exception as e:
        logger.warning("Upload-Bremse nicht erreichbar (Redis), lasse durch: {}", e)
        return ticket


def _release_upload_slot(ticket: str) -> None:
    try:
        _redis().zrem(_UPLOAD_SET_KEY, ticket)
    except Exception as e:
        # No drama: the entry drops out by itself after _UPLOAD_STALE_SECONDS.
        logger.warning("Upload-Platz konnte nicht freigegeben werden: {}", e)




@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources")
async def upload_source(
    workspace_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)

    # Only check, do not count, so a rejection uses up no slot.
    check_upload_limit(current_user["user_id"], locale=locale)

    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    # Existing filenames, normalized for a case-insensitive duplicate check below.
    existing_names = {(s["filename"] or "").strip().lower() for s in existing_sources}

    # Limit from the admin area, otherwise the value from the code.
    raw_limit = db.get_setting("aia_workspace_max_sources", str(AIA_WORKSPACE_MAX_SOURCES))
    try:
        max_sources = int(raw_limit)
    except (TypeError, ValueError):
        max_sources = AIA_WORKSPACE_MAX_SOURCES
    if len(existing_sources) >= max_sources:
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.maxPerWorkspace", locale, max=max_sources, label=_workspace_label(locale)),
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t("ai.source.allowedExtensions", locale, extensions=", ".join(sorted(_ALLOWED_EXTENSIONS))),
        )

    # Reject same-named uploads early, office files are checked again after conversion.
    if file.filename.strip().lower() in existing_names:
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.duplicateName", locale, name=file.filename, label=_workspace_label(locale)),
        )

    # Whoever gets no slot receives 503 and can try again right away.
    ticket = _claim_upload_slot(_max_concurrent_uploads())
    if ticket is None:
        raise HTTPException(status_code=503, detail=t("ai.source.serverBusy", locale))
    try:
        # Stream onto a temp file and keep every heavy step outside the event loop.
        with tempfile.TemporaryDirectory(prefix="aia_upload_") as tmpdir:
            raw_path = str(Path(tmpdir) / f"input{ext}")
            total, head = await stream_upload_to_path(file, raw_path, _MAX_UPLOAD_BYTES, locale)
            if total == 0:
                raise HTTPException(status_code=400, detail=t("file.empty", locale))
            validate_or_raise(head, ext, locale)

            stored_filename = file.filename
            final_path = raw_path
            if ext in (".docx", ".pptx"):
                logger.info("KI Tutor: converting {} to PDF ({})", ext, file.filename)
                final_path = await asyncio.to_thread(_convert_office_to_pdf_path, raw_path, ext, tmpdir, locale)
                stored_filename = Path(file.filename).stem + ".pdf"
                ext = ".pdf"
                # The converted name can now collide with an existing source.
                if stored_filename.strip().lower() in existing_names:
                    raise HTTPException(
                        status_code=409,
                        detail=t("ai.source.duplicateName", locale, name=stored_filename, label=_workspace_label(locale)),
                    )
            elif ext == ".mp4":
                logger.info("KI Tutor: applying MP4 faststart ({})", file.filename)
                final_path = await asyncio.to_thread(_mp4_faststart_path, raw_path, tmpdir)

            page_count = await asyncio.to_thread(_count_pages_path, ext, final_path)
            # Page limit from the admin area, otherwise the value from the code.
            try:
                max_pages = int(db.get_setting("aia_source_max_pages", str(AIA_SOURCE_MAX_PAGES)))
            except (TypeError, ValueError):
                max_pages = AIA_SOURCE_MAX_PAGES
            if page_count is not None and page_count > max_pages:
                raise HTTPException(
                    status_code=413,
                    detail=t("ai.source.tooManyPages", locale, pages=page_count, max=max_pages),
                )

            source_uuid = uuid.uuid4().hex
            file_type = ext.lstrip(".")
            # The file hangs off the owner, not off the uploader.
            file_path = await asyncio.to_thread(
                _save_source_file_path, workspace["user_id"], workspace_uuid, source_uuid, ext, final_path
            )

            db.create_aia_source(
                workspace_id=workspace["id"],
                uuid=source_uuid,
                filename=stored_filename,
                file_path=file_path,
                file_type=file_type,
            )

            from src.features.ai_assistant.scheduling.service import scheduler_enabled, enqueue_task
            if scheduler_enabled():
                enqueue_task("aia.index_source", current_user["user_id"], args=[source_uuid, locale])
            else:
                from src.tasks.aia_tasks import run_index_source
                run_index_source.delay(source_uuid, locale)

            # Only count now, every rejection above reversed it before.
            record_upload(current_user["user_id"])

            logger.info("KI Tutor: source {} ({}) uploaded to workspace {}", source_uuid, stored_filename, workspace_uuid)
            return {"uuid": source_uuid, "filename": stored_filename, "status": "pending"}
    finally:
        _release_upload_slot(ticket)


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/retry")
async def retry_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Binds the source to your own course room.
    source = _load_workspace_source(source_uuid, workspace, locale)
    # Two ways in: a broken source or one with open pages.
    ocr_open = bool((source.get("ocr_info") or {}).get("open"))
    catching_up_ocr = source["status"] == "ready" and ocr_open
    if source["status"] != "failed" and not catching_up_ocr:
        raise HTTPException(status_code=409, detail=t("ai.source.retryFailedOnly", locale))

    db.delete_aia_chunks_by_source(source["id"])
    db.reset_aia_source_for_retry(source_uuid)

    from src.features.ai_assistant.scheduling.service import scheduler_enabled, enqueue_task
    if scheduler_enabled():
        enqueue_task("aia.index_source", current_user["user_id"], args=[source_uuid, locale])
    else:
        from src.tasks.aia_tasks import run_index_source
        run_index_source.delay(source_uuid, locale)

    logger.info("KI Tutor: source {} retry dispatched", source_uuid)
    return {"uuid": source_uuid, "status": "pending"}


@router.delete("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}")
def delete_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Binds the source to your own course room.
    source = _load_workspace_source(source_uuid, workspace, locale)
    try:
        delete_aia_source_files(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source files for {}: {}", source["file_path"], e)
    db.delete_aia_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}
