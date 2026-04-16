"""KI-Assistent routes — popup actions."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.limits import (
    TUTOR_SOURCE_MAX_PAGES,
    TUTOR_MODULE_MAX_SOURCES,
    TUTOR_MODULE_MAX_ACCESS_LINKS,
    TUTOR_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import (
    TUTOR_SYSTEM_DIRECT,
    TUTOR_SYSTEM_DIRECT_WITH_CONTEXT,
    TUTOR_SYSTEM_RAG,
    TUTOR_POPUP_ACTIONS,
)

from src.features.ki_assistent.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _strip_image_text_layer,
    _markdown_fallback,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])

@router.get("/ki-assistent/popup-actions")
async def get_popup_actions():
    """Liefert die konfigurierten Popup-Aktionen für den PDF-Viewer."""
    return {
        "actions": [
            {
                "key": a["key"],
                "label": a["label"],
                "icon": a["icon"],
                "prompt": a["prompt"],
                "min_words": a["min_words"],
            }
            for a in TUTOR_POPUP_ACTIONS
        ]
    }

