"""Changing the cast after the start, so a podcast can be recast without a new one."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.features.podcast import store
from src.features.podcast.schemas import Person
from src.i18n import get_locale, t
from src.routes.podcast._shared import own_job, pruefe_params

router = APIRouter(tags=["podcast"])


class ParamsRequest(BaseModel):
    """Only what the cast step shows, the rest of the settings stays as it was."""

    persons: list[Person]
    length: str = "medium"
    style: str = "teaching"


@router.put("/podcast/{job_uuid}/params")
async def put_params(
    job_uuid: str,
    body: ParamsRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """A new cast, saved so the next voicing speaks the changed contributions again."""
    job = own_job(job_uuid, current_user, locale)
    user_id = job["user_id"]
    if job["status"] in ("running", "pending", "queued"):
        raise HTTPException(status_code=409, detail=t("podcast.running", locale))

    alt = store.load_params(user_id, job_uuid)
    if not alt:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))

    # Language and material steered the writing and the writing is done, so they stay.
    neu = alt.model_copy(update={
        "persons": body.persons,
        "length": body.length,
        "style": body.style,
        "provider_id": body.persons[0].provider_id if body.persons else alt.provider_id,
    })
    pruefe_params(neu, locale)
    store.save_params(user_id, job_uuid, neu)

    # A contribution of a person who is gone is wrapped around, the same rule the writer uses:
    # capping to 0 would hand the whole rest of the conversation to one voice.
    zeilen = store.load_lines(user_id, job_uuid)
    gezogen = [l.model_copy(update={"speaker": l.speaker % len(neu.persons)})
               if l.speaker >= len(neu.persons) else l for l in zeilen]
    if gezogen != zeilen:
        store.save_user_script(user_id, job_uuid, gezogen)

    logger.info("Podcast {}: Besetzung geändert auf {} Personen", job_uuid[:8], len(neu.persons))
    return {"persons": [p.model_dump() for p in neu.persons]}
