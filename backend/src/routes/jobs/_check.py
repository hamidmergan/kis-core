"""Checks working jobs and the storage limit before a form starts a job."""

from fastapi import APIRouter, Depends

from src import database as db
from src.dependencies import get_current_user


router = APIRouter()

@router.get("/check/{tool_group}")
def check_job_limit(
    tool_group: str,  # noqa: ARG001 - the limit counts all tools, the path keeps its shape
    current_user: dict = Depends(get_current_user),
):
    """Check if user can start a new job: too many working? Storage limit reached?"""
    user_id = current_user.get("user_id", 0)

    from src.services.open_jobs import at_limit
    from src.services.tool_limits import results_kept_per_user

    # The same rule the start routes apply, so the form never promises too much.
    has_active = at_limit(user_id)

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
