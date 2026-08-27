"""Shared imports for the sources sub-routers."""
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

from src.features.ai_assistant.routes._helpers import (
    _convert_office_to_pdf,
    _mp4_faststart,
    _count_pages,
    _convert_office_to_pdf_path,
    _mp4_faststart_path,
    _count_pages_path,
    _require_workspace_manage,
    _save_source_file_path,
    _ALLOWED_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
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
    "_ALLOWED_EXTENSIONS", "_MAX_UPLOAD_BYTES",
]
