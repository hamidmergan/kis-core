"""GET /jobs/check/{tool_group} - prüft aktive Jobs + Storage-Limit."""

from fastapi import APIRouter, Depends

from src import database as db
from src.dependencies import get_current_user
from src.limits import MAX_QUEUED_SCREENCAST_JOBS


router = APIRouter()

_TOOL_GROUP_TOOLS = {
    "screencast": ["screencast_translate", "screencast_render"],
    "tts": ["tts"],
}

_TOOL_GROUP_LIMITS = {
    "screencast": MAX_QUEUED_SCREENCAST_JOBS,
}


@router.get("/check/{tool_group}")
async def check_job_limit(
    tool_group: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if user can start a new job: active job exists? Storage limit reached?"""
    user_id = current_user.get("user_id", 0)

    tools = _TOOL_GROUP_TOOLS.get(tool_group, [])
    max_jobs = _TOOL_GROUP_LIMITS.get(tool_group, 1)
    has_active = db.count_all_jobs_for_tool(user_id, tools) >= max_jobs if tools else False

    # Was faellt raus, wenn jetzt EIN Auftrag dazukommt? Deshalb cap - 1: der neue
    # Auftrag belegt selbst einen der Plaetze im Vorrat.
    from src.database import MAX_RESULT_FILES
    vorhanden = db.get_jobs_for_user_newest_first(user_id)
    faellig = db.select_jobs_to_evict(vorhanden, cap=MAX_RESULT_FILES - 1)
    at_storage_limit = bool(faellig)
    evict_filename = None
    if at_storage_limit:
        aeltester = faellig[-1]  # neueste zuerst, also steht das Aelteste hinten
        evict_filename = aeltester.get("original_filename") or aeltester.get("result_filename")

    return {
        "has_active_job": has_active,
        "at_storage_limit": at_storage_limit,
        "evict_filename": evict_filename,
    }
