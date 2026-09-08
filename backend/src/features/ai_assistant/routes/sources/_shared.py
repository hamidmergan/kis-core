"""Shared imports and the common tail every new source goes through."""
import asyncio
import uuid as _uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.limits import (
    AIA_MAX_CONCURRENT_UPLOADS,
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
)
from src.storage import (
    USE_S3,
    aia_transcript_prefix,
    aia_vtt_key,
    delete_aia_source_files,
    file_exists,
    get_file,
    list_keys,
    stream_s3_object,
)

from src.features.ai_assistant.routes._media_files import (
    _ALLOWED_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
    _convert_office_to_pdf,
    _convert_office_to_pdf_path,
    _count_pages,
    _count_pages_path,
    _mp4_faststart,
    _mp4_faststart_path,
)
from src.features.ai_assistant.routes._workspace_access import (
    _require_workspace_manage,
    _save_source_file_path,
)

def _load_workspace_source(source_uuid: str, workspace: dict, locale: str) -> dict:
    """Fetches a source and binds it to the course room, otherwise 404."""
    source = db.get_aia_source(source_uuid)
    if not source or source["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))
    return source


def _workspace_label(locale: str) -> str:
    """The label the admin set for a course room."""
    key = "workspace_label_singular_en" if locale == "en" else "workspace_label_singular_de"
    return db.get_setting(key, db.get_setting("workspace_label_singular", "Modul"))


def _require_source_capacity(existing_sources: list[dict], locale: str) -> None:
    """Rejects a new source once the course room holds as many as the admin allows."""
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


async def _register_source_file(
    workspace: dict,
    workspace_uuid: str,
    final_path: str,
    ext: str,
    stored_filename: str,
    actor_user_id: int,
    locale: str,
    source_url: str | None = None,
) -> dict:
    """Page cap, storage, table row and ingest job, the tail every new source goes through."""
    page_count = await asyncio.to_thread(_count_pages_path, ext, final_path)
    try:
        max_pages = int(db.get_setting("aia_source_max_pages", str(AIA_SOURCE_MAX_PAGES)))
    except (TypeError, ValueError):
        max_pages = AIA_SOURCE_MAX_PAGES
    if page_count is not None and page_count > max_pages:
        raise HTTPException(
            status_code=413,
            detail=t("ai.source.tooManyPages", locale, pages=page_count, max=max_pages),
        )

    source_uuid = _uuid.uuid4().hex
    # The file hangs off the owner, not off the person adding it.
    file_path = await asyncio.to_thread(
        _save_source_file_path, workspace["user_id"], workspace_uuid, source_uuid, ext, final_path
    )
    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=source_uuid,
        filename=stored_filename,
        file_path=file_path,
        file_type=ext.lstrip("."),
        source_url=source_url,
    )

    from src.features.ai_assistant.scheduling.service import scheduler_enabled, enqueue_task
    if scheduler_enabled():
        enqueue_task("aia.index_source", actor_user_id, args=[source_uuid, locale])
    else:
        from src.tasks.aia_tasks import run_index_source
        run_index_source.delay(source_uuid, locale)
    return {"uuid": source_uuid, "filename": stored_filename, "status": "pending", "source_url": source_url}


__all__ = [
    "Path", "Optional",
    "APIRouter", "Depends", "File", "HTTPException", "Request", "UploadFile",
    "FileResponse", "Response", "StreamingResponse",
    "logger", "db",
    "get_current_user",
    "get_locale", "t",
    "AIA_MAX_CONCURRENT_UPLOADS", "AIA_SOURCE_MAX_PAGES", "AIA_WORKSPACE_MAX_SOURCES",
    "USE_S3", "delete_aia_source_files", "file_exists", "get_file", "list_keys",
    "stream_s3_object", "aia_transcript_prefix", "aia_vtt_key",
    "_convert_office_to_pdf", "_mp4_faststart", "_count_pages",
    "_convert_office_to_pdf_path", "_mp4_faststart_path", "_count_pages_path",
    "_require_workspace_manage", "_load_workspace_source", "_workspace_label",
    "_save_source_file_path",
    "_require_source_capacity", "_register_source_file",
    "_ALLOWED_EXTENSIONS", "_MAX_UPLOAD_BYTES",
]
