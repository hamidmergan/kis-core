"""What the chat settles before the answer: level block, sources, selection note."""

from typing import Optional

from fastapi import HTTPException

from src import database as db
from src.i18n import t
from src.features.ai_assistant.prompts.popup_prompts import AIA_POPUP_ACTIONS
from src.services.aia_adaptive_chat import (
    DEFAULT_ADAPTIVE_BEHAVIOR,
    _LEGACY_ADAPTIVE_BEHAVIOR,
    adaptive_chat_appendix,
    level_texts,
    seal_adaptive_suffix,
)
from src.services.aia_diagnosis_chat import ADAPTIVE_BEHAVIOR_SETTING
from src.services.aia_level_ladder import resolve_prompt_setting


def adaptive_suffix_for(user_id: int) -> tuple[str, Optional[str]]:
    """The sealed block for the user message and the level it was written for."""
    suffix, applied_level = "", None
    # Level-appropriate answers need the person's switch and a stored level.
    if db.is_language_training_ready(user_id):
        # The level block hangs on the user message, where it weighs most.
        level = db.get_user_language_level(user_id)["language_level"]
        example, description = level_texts(level)
        suffix, applied_level = adaptive_chat_appendix(
            level,
            resolve_prompt_setting(
                db.get_setting(ADAPTIVE_BEHAVIOR_SETTING, ""),
                _LEGACY_ADAPTIVE_BEHAVIOR,
                DEFAULT_ADAPTIVE_BEHAVIOR,
            ),
            example,
            description,
        )
    # The source guard goes along with every chat and always stays last.
    return seal_adaptive_suffix(suffix), applied_level


def heal_workspace_status(workspace: dict, locale: str) -> None:
    """Sets a stale 'pending' to ready, without a single indexed source the chat refuses."""
    if workspace["status"] == "ready":
        return
    sources = db.get_aia_sources_by_workspace(workspace["id"])
    if not any(s["status"] == "ready" for s in sources):
        raise HTTPException(status_code=409, detail=t("ai.chat.noIndexedSources", locale))
    if all(s["status"] == "ready" for s in sources):
        db.update_aia_workspace_status(workspace["uuid"], "ready")


def resolve_active_sources(active_source_uuids: Optional[list[str]],
                           workspace_id: int) -> tuple[Optional[list[int]], dict[int, dict]]:
    """The ticked sources of this workspace as ids and rows, None when nothing usable is ticked."""
    ids: list[int] = []
    rows: dict[int, dict] = {}
    for suuid in active_source_uuids or []:
        source = db.get_aia_source(suuid)
        if source and source["workspace_id"] == workspace_id:
            ids.append(source["id"])
            rows[source["id"]] = source
    return (ids or None), rows


def popup_selection_entry(body) -> Optional[dict]:
    """The note about the marked text, None when the question is no selection action."""
    if not (body.source_text and body.source_uuid and body.source_page):
        return None
    entry = {
        "source_uuid": body.source_uuid,
        "filename": body.source_filename or "",
        "page_number": body.source_page,
        "source_text": body.source_text,
        "is_popup_selection": True,
    }
    action = next((a for a in AIA_POPUP_ACTIONS if a["key"] == body.action_key), None) \
        if body.action_key else None
    if action:
        entry["action_key"] = body.action_key
        entry["action_icon"] = action["icon"]
    return entry
