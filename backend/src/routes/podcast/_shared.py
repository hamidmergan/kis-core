"""What every podcast route needs: the job of this person, nothing else."""

import re

from fastapi import HTTPException

from src import database as db
from src.i18n import t

_UUID = re.compile(r"^[a-f0-9]{32}$")


def own_job(job_uuid: str, current_user: dict, locale: str) -> dict:
    """Missing and foreign answer alike, otherwise a uuid could be guessed."""
    if not _UUID.match(job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(job_uuid)
    if not job or job["tool"] != "podcast" or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    return job
