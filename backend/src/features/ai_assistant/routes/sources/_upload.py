"""Source upload / retry / delete."""
import asyncio
import tempfile
import uuid

from src.security.rate_limit import check_upload_limit, record_upload
from src.utils.file_validation import validate_or_raise

from ._shared import (
    Path, APIRouter, Depends, File, HTTPException, UploadFile, logger, db,
    get_current_user, get_locale, t,
    AIA_MAX_CONCURRENT_UPLOADS, AIA_SOURCE_MAX_PAGES, AIA_WORKSPACE_MAX_SOURCES,
    delete_file, _convert_office_to_pdf_path, _mp4_faststart_path, _count_pages_path,
    _require_own_workspace, _save_source_file_path,
    _ALLOWED_EXTENSIONS, _MAX_UPLOAD_BYTES,
)

router = APIRouter(tags=["ki-assistent: sources"])

# Global cap on simultaneous uploads in the heavy (stream + convert + store)
# phase. One uvicorn worker = one event loop, so a plain int is race-free as long
# as the check and the increment run with no await between them (they do, below).
_uploads_in_flight = 0

_UPLOAD_CHUNK = 1024 * 1024  # 1 MiB per stream chunk


def _max_concurrent_uploads() -> int:
    """Admin-tunable upload concurrency cap (0 = unlimited)."""
    try:
        return max(0, int(db.get_setting("aia_max_concurrent_uploads", str(AIA_MAX_CONCURRENT_UPLOADS))))
    except (TypeError, ValueError):
        return AIA_MAX_CONCURRENT_UPLOADS


async def _stream_to_tempfile(file: UploadFile, dest_path: str, max_bytes: int, locale: str) -> tuple[int, bytes]:
    """Stream the request body to ``dest_path`` in chunks so a large upload never
    sits fully in RAM. Returns ``(total_bytes, head)`` where ``head`` is the first
    64 KiB (enough for magic-byte / UTF-8 content validation). Raises 413 as soon
    as the body exceeds ``max_bytes``."""
    total = 0
    head = bytearray()
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(_UPLOAD_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=t("file.tooLargeMb", locale, max=max_bytes // (1024 * 1024)),
                )
            if len(head) < 65536:
                head.extend(chunk[: 65536 - len(head)])
            out.write(chunk)
    return total, bytes(head)


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources")
async def upload_source(
    workspace_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)

    # Reject before reading the body so spam attempts don't waste bandwidth.
    # READ-ONLY check here; the counter is bumped by record_upload() only once the
    # upload is fully accepted below, so a duplicate / over-max-sources /
    # over-max-pages / bad-file rejection never consumes a slot. Concurrent
    # throughput is bounded by the Celery worker; the per-workspace ceiling is
    # enforced just below.
    check_upload_limit(current_user["user_id"], locale=locale)

    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    # Existing filenames, normalized for a case-insensitive duplicate check below.
    existing_names = {(s["filename"] or "").strip().lower() for s in existing_sources}

    def _ws_label() -> str:
        # Admin-configured workspace label (e.g. "Modul", "Kurs") so error
        # messages match whatever students see elsewhere in the UI.
        label_key = "workspace_label_singular_en" if locale == "en" else "workspace_label_singular_de"
        return db.get_setting(label_key, db.get_setting("workspace_label_singular", "Workspace"))

    # Limit is admin-tunable at runtime via the settings tab; fall back to the
    # code constant when the DB setting is missing or unparseable.
    raw_limit = db.get_setting("aia_workspace_max_sources", str(AIA_WORKSPACE_MAX_SOURCES))
    try:
        max_sources = int(raw_limit)
    except (TypeError, ValueError):
        max_sources = AIA_WORKSPACE_MAX_SOURCES
    if len(existing_sources) >= max_sources:
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.maxPerWorkspace", locale, max=max_sources, label=_ws_label()),
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t("ai.source.allowedExtensions", locale, extensions=", ".join(sorted(_ALLOWED_EXTENSIONS))),
        )

    # Reject same-name uploads early (before reading the body) so a re-uploaded
    # file is bounced cheaply. Office files get a second check after the PDF
    # rename below, since their stored name changes.
    if file.filename.strip().lower() in existing_names:
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.duplicateName", locale, name=file.filename, label=_ws_label()),
        )

    # Global concurrency gate. Race-free: the limit read + the check + the
    # increment run with no await between them (single event loop). A rejected
    # caller gets a 503 so the client can retry instead of overloading the box.
    global _uploads_in_flight
    limit = _max_concurrent_uploads()
    if 0 < limit <= _uploads_in_flight:
        raise HTTPException(status_code=503, detail=t("ai.source.serverBusy", locale))
    _uploads_in_flight += 1
    try:
        # Stream the body to a temp file on disk, then run every heavy step
        # (validate, convert, faststart, page-count, store) off the event loop so
        # one upload can't freeze the single-worker backend for everyone else.
        with tempfile.TemporaryDirectory(prefix="aia_upload_") as tmpdir:
            raw_path = str(Path(tmpdir) / f"input{ext}")
            total, head = await _stream_to_tempfile(file, raw_path, _MAX_UPLOAD_BYTES, locale)
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
                # The converted name (e.g. lecture.docx -> lecture.pdf) may now
                # collide with an existing source even though the original did not.
                if stored_filename.strip().lower() in existing_names:
                    raise HTTPException(
                        status_code=409,
                        detail=t("ai.source.duplicateName", locale, name=stored_filename, label=_ws_label()),
                    )
            elif ext == ".mp4":
                logger.info("KI Tutor: applying MP4 faststart ({})", file.filename)
                final_path = await asyncio.to_thread(_mp4_faststart_path, raw_path, tmpdir)

            page_count = await asyncio.to_thread(_count_pages_path, ext, final_path)
            # Max pages per source is admin-tunable at runtime (settings tab); fall
            # back to the code constant when the DB setting is missing or unparseable.
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
            file_path = await asyncio.to_thread(
                _save_source_file_path, current_user["user_id"], workspace_uuid, source_uuid, ext, final_path
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

            # Count toward the hourly cap ONLY now that the upload is fully accepted —
            # every reject path above returned before here, so errors don't burn a slot.
            record_upload(current_user["user_id"])

            logger.info("KI Tutor: source {} ({}) uploaded to workspace {}", source_uuid, stored_filename, workspace_uuid)
            return {"uuid": source_uuid, "filename": stored_filename, "status": "pending"}
    finally:
        _uploads_in_flight -= 1


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/retry")
async def retry_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))
    if source["status"] != "failed":
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
async def delete_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))
    try:
        delete_file(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source file {}: {}", source["file_path"], e)
    db.delete_aia_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}
