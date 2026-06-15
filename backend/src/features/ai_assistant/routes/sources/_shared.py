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
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, list_keys, stream_s3_object

from src.features.ai_assistant.routes._helpers import (
    _convert_office_to_pdf,
    _mp4_faststart,
    _count_pages,
    _require_own_workspace,
    _save_source_file,
    _ALLOWED_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)

__all__ = [
    "Path", "Optional",
    "APIRouter", "Depends", "File", "HTTPException", "Request", "UploadFile",
    "FileResponse", "Response", "StreamingResponse",
    "logger", "db",
    "get_current_user",
    "get_locale", "t",
    "AIA_SOURCE_MAX_PAGES", "AIA_WORKSPACE_MAX_SOURCES",
    "USE_S3", "delete_file", "file_exists", "get_file", "list_keys", "stream_s3_object",
    "_convert_office_to_pdf", "_mp4_faststart", "_count_pages",
    "_require_own_workspace", "_save_source_file",
    "_ALLOWED_EXTENSIONS", "_MAX_UPLOAD_BYTES",
]
