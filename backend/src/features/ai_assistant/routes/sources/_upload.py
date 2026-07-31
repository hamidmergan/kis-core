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
    _ALLOWED_EXTENSIONS, _MAX_UPLOAD_BYTES,
)

router = APIRouter(tags=["ki-assistent: sources"])

# Globale Bremse für gleichzeitige Uploads in der schweren Phase (streamen,
# umwandeln, ablegen). Der Zähler liegt in Redis, nicht mehr als int im Prozess:
# bei mehreren uvicorn-Prozessen hätte jeder seinen eigenen gezählt, aus einer
# Grenze von 3 wären bei 3 Prozessen faktisch 9 geworden. Genau der Schutz, der
# die kleine Box am Leben hält, wäre damit weg gewesen.
#
# Umsetzung als sortierte Menge mit Zeitstempeln statt als INCR/DECR-Zähler.
# Grund: wird ein Prozess hart abgeschossen, läuft das DECR nie und der Zähler
# bliebe für immer zu hoch. Einträge mit altem Zeitstempel fallen dagegen von
# selbst heraus.
_UPLOAD_SET_KEY = "kis:uploads:inflight"
# Wie lange ein Eintrag höchstens gilt. Großzügig, damit ein echter langer
# Upload (großes Video, Office-Umwandlung) nie fälschlich verworfen wird. Ein
# verwaister Platz heilt entsprechend nach dieser Zeit von selbst.
_UPLOAD_STALE_SECONDS = 15 * 60

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")


def _redis():
    """Redis-Client mit kurzen Zeitgrenzen, gleiches Muster wie rate_limit.py."""
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _max_concurrent_uploads() -> int:
    """Admin-tunable upload concurrency cap (0 = unlimited)."""
    try:
        return max(0, int(db.get_setting("aia_max_concurrent_uploads", str(AIA_MAX_CONCURRENT_UPLOADS))))
    except (TypeError, ValueError):
        return AIA_MAX_CONCURRENT_UPLOADS


def _claim_upload_slot(limit: int) -> str | None:
    """Einen Upload-Platz belegen. Gibt die Kennung zurück, oder None wenn voll.

    ``limit <= 0`` heißt unbegrenzt, dann wird nur mitgezählt.

    Bei Redis-Ausfall wird AUF gemacht (Upload erlaubt). Die Bremse schützt vor
    Überlast, sie ist kein Sicherheitsmerkmal, und ein Redis-Ausfall darf nicht
    dazu führen, dass niemand mehr Dateien hochladen kann.
    """
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
        # Kein Drama: der Eintrag fällt nach _UPLOAD_STALE_SECONDS von selbst raus.
        logger.warning("Upload-Platz konnte nicht freigegeben werden: {}", e)




@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources")
async def upload_source(
    workspace_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)

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

    # Globale Bremse, jetzt prozessübergreifend über Redis. Wer keinen Platz
    # bekommt, erhält 503 und kann es gleich nochmal versuchen, statt die Box
    # zusätzlich zu belasten.
    ticket = _claim_upload_slot(_max_concurrent_uploads())
    if ticket is None:
        raise HTTPException(status_code=503, detail=t("ai.source.serverBusy", locale))
    try:
        # Stream the body to a temp file on disk, then run every heavy step
        # (validate, convert, faststart, page-count, store) off the event loop so
        # one upload can't freeze the single-worker backend for everyone else.
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
            # Key the file to the workspace OWNER, not whoever uploaded it. A
            # tutor uploading into someone else's workspace must not scatter its
            # files across a second prefix, or deleting the workspace would miss them.
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

            # Count toward the hourly cap ONLY now that the upload is fully accepted —
            # every reject path above returned before here, so errors don't burn a slot.
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
    # Bind the source to the owned workspace: without this an owner of workspace A
    # could retry (delete chunks + reset) a source belonging to workspace B.
    source = _load_workspace_source(source_uuid, workspace, locale)
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
def delete_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Bind the source to the owned workspace: without this an owner of workspace A
    # could delete a source (file + DB row) belonging to workspace B.
    source = _load_workspace_source(source_uuid, workspace, locale)
    try:
        delete_aia_source_files(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source files for {}: {}", source["file_path"], e)
    db.delete_aia_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}
