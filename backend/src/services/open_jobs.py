"""One rule for all tools: how many jobs a person may have working at once.

The number counts real load across tools, but services with a voice and services without one
count apart: a voicing waits on the voice provider and must never hold up a transcript. A job
parked for the person does not count, it occupies nobody.
"""

from fastapi import HTTPException

from src import database as db
from src.features.jobs.repository._crud import TooManyOpenJobs
from src.features.jobs.repository._queries import VOICE_TOOLS
from src.i18n import t
from src.services.tool_limits import max_open_jobs


def at_limit(user_id: int, tool: str) -> bool:
    """True when no slot of this tool's kind is left, ``-1`` means the way is always open."""
    grenze = max_open_jobs()
    return grenze >= 0 and db.count_working_jobs(user_id, voice=tool in VOICE_TOOLS) >= grenze


def enforce_open_jobs(user_id: int, locale: str, tool: str) -> None:
    """Refuses a new job while the person already has too many of its kind working."""
    if at_limit(user_id, tool):
        # The number is the admin's business, the person only needs to wait.
        raise HTTPException(status_code=409, detail=t("job.tooManyOpen", locale))


def create_counted_job(job_uuid: str, user_id: int, tool: str, original_filename: str, locale: str = "de") -> None:
    """Creates the job only while the person is below the limit, checked and inserted in one step."""
    try:
        db.create_job(job_uuid, user_id, tool, original_filename, locale=locale, limit=max_open_jobs())
    except TooManyOpenJobs:
        raise HTTPException(status_code=409, detail=t("job.tooManyOpen", locale))
