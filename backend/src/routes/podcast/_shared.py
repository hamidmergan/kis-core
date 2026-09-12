"""What every podcast route needs: the job of this person, nothing else."""

import re

from fastapi import HTTPException

from src import database as db
from src.features.podcast.schemas import LANGUAGES, LENGTH_WORDS, ROLES, STYLES, PodcastParams
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


def pruefe_params(params: PodcastParams, locale: str) -> PodcastParams:
    """The cast rules, shared by the start and by a later recast."""
    if not 1 <= len(params.persons) <= 4:
        raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
    if params.language not in LANGUAGES or params.length not in LENGTH_WORDS or params.style not in STYLES:
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale))
    for person in params.persons:
        if person.role not in ROLES or not person.voice_id or person.provider_id <= 0:
            raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
    return params
