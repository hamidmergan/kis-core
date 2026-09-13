"""One rule for all tools: how many jobs a person may have working at once.

The number counts real load, so it counts across tools rather than per tool: the
workers are shared. A job parked for the person does not count, it occupies nobody.
"""

from fastapi import HTTPException

from src import database as db
from src.i18n import t
from src.services.tool_limits import max_open_jobs


def at_limit(user_id: int) -> bool:
    """True when no slot is left, ``-1`` means the way is always open."""
    grenze = max_open_jobs()
    return grenze >= 0 and db.count_working_jobs(user_id) >= grenze


def enforce_open_jobs(user_id: int, locale: str = "de") -> None:
    """Refuses a new job while the person already has too many working."""
    if at_limit(user_id):
        # The number is the admin's business, the person only needs to wait.
        raise HTTPException(status_code=409, detail=t("job.tooManyOpen", locale))
