"""What every podcast route needs: the job of this person, nothing else."""

from fastapi import HTTPException

from src.features.podcast.schemas import (
    LANGUAGES,
    LENGTH_WORDS,
    ROLES,
    SPEED_MAX,
    SPEED_MIN,
    STYLES,
    PodcastParams,
)
from src.i18n import t
from src.routes import _shared


def own_job(job_uuid: str, current_user: dict, locale: str) -> dict:
    """The podcast job of this person."""
    return _shared.own_job(job_uuid, current_user, locale, tool="podcast")


def pruefe_params(params: PodcastParams, locale: str, user: dict | None = None) -> PodcastParams:
    """The cast rules, shared by the start and by a later recast."""
    if not 1 <= len(params.persons) <= 4:
        raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
    if params.language not in LANGUAGES or params.length not in LENGTH_WORDS or params.style not in STYLES:
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale))
    if not SPEED_MIN <= params.speed <= SPEED_MAX:
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale))
    for person in params.persons:
        if person.role not in ROLES or not person.voice_id or person.provider_id <= 0:
            raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
        if user is not None:
            from src.services.own_tts.access import check_voice_provider
            check_voice_provider(person.provider_id, user, locale)
    return params
