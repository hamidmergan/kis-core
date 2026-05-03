"""KI-Assistent routes - popup actions."""

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
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale
from src.limits import (
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
    AIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    AIA_SYSTEM_RAG,
    AIA_POPUP_ACTIONS,
)

from src.features.ai_assistant.routes._helpers import (
    _trace_llm,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_workspace,
    _save_source_file,
    _delete_source_files_for_workspace,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: popup"])

@router.get("/ai-assistant/popup-actions")
async def get_popup_actions(locale: str = Depends(get_locale)):
    """Return the PDF-viewer popup actions in the user's UI locale.

    Both label and prompt match the locale; the prompts instruct the LLM to
    answer in the source-text language, so they're behaviourally equivalent
    across locales and only differ in tone.
    """
    label_key = "label_en" if locale == "en" else "label_de"
    prompt_key = "prompt_en" if locale == "en" else "prompt_de"
    return {
        "actions": [
            {
                "key": a["key"],
                "label": a[label_key],
                "icon": a["icon"],
                "prompt": a[prompt_key],
                "min_words": a["min_words"],
            }
            for a in AIA_POPUP_ACTIONS
        ]
    }

