"""Checks active jobs and the storage limit for a tool group."""

from fastapi import APIRouter, Depends

from src import database as db
from src.dependencies import get_current_user


router = APIRouter()

_TOOL_GROUP_TOOLS = {
    "screencast": ["screencast_translate", "screencast_render"],
    "tts": ["tts"],
}


@router.get("/check/{tool_group}")
async def check_job_limit(
    tool_group: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if user can start a new job: active job exists? Storage limit reached?"""
    user_id = current_user.get("user_id", 0)

    from src.services.tool_limits import max_open_screencast_jobs, results_kept_per_user

    tools = _TOOL_GROUP_TOOLS.get(tool_group, [])
    max_jobs = max_open_screencast_jobs() if tool_group == "screencast" else 1
    # -1 means unlimited, then the way is always open.
    has_active = (
        bool(tools) and max_jobs >= 0
        and db.count_all_jobs_for_tool(user_id, tools) >= max_jobs
    )

    # cap - 1, because the new job takes a slot itself.
    vorrat = results_kept_per_user()
    vorhanden = db.get_jobs_for_user_newest_first(user_id)
    faellig = db.select_jobs_to_evict(vorhanden, cap=vorrat if vorrat < 0 else vorrat - 1)
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
