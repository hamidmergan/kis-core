"""Reading the state and saving the checked script."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user
from src.features.podcast import store
from src.features.podcast.schemas import Line
from src.i18n import get_locale, t
from src.limits import PODCAST_MAX_CHARS, PODCAST_MAX_LINE_CHARS, PODCAST_MAX_LINES
from src.routes.podcast._shared import own_job

router = APIRouter(tags=["podcast"])


def _fortschritt(roh) -> dict | None:
    """The database keeps the progress as text, the page needs the object."""
    if not roh:
        return None
    if isinstance(roh, dict):
        return roh
    try:
        return json.loads(roh)
    except (TypeError, ValueError):
        return None


class ScriptRequest(BaseModel):
    """The list as the person left it, order included."""

    lines: list[Line]


@router.get("/podcast/{job_uuid}")
async def get_podcast(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Everything the page needs to come back to where it left off."""
    job = own_job(job_uuid, current_user, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    zeilen = store.load_lines(user_id, job_uuid)
    vertont = store.load_voiced(user_id, job_uuid)
    return {
        "job_uuid": job_uuid,
        "status": job["status"],
        "progress": _fortschritt(job.get("progress")),
        "error": job.get("error_message"),
        "params": params.model_dump() if params else None,
        "lines": [l.model_dump() for l in zeilen],
        # Which contributions carry the audio of exactly this text right now.
        "voiced": [
            l.id for l in zeilen
            if not store.needs_voice(
                l, vertont,
                params.persons[l.speaker].voice_id if params and l.speaker < len(params.persons) else "",
                1.0,
            )
        ] if params else [],
        "has_result": bool(job.get("result_path")),
    }


@router.put("/podcast/{job_uuid}/script")
async def put_script(
    job_uuid: str,
    body: ScriptRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Saved on every change, so a closed tab loses nothing."""
    job = own_job(job_uuid, current_user, locale)
    if job["status"] in ("running", "pending", "queued", "waiting_retry"):
        raise HTTPException(status_code=409, detail=t("podcast.running", locale))

    # Say it out loud, quietly dropping the 251st contribution loses somebody's work.
    if len(body.lines) > PODCAST_MAX_LINES:
        raise HTTPException(status_code=422, detail=t(
            "podcast.tooManyLines", locale, lines=len(body.lines), max=PODCAST_MAX_LINES))
    zeichen = sum(len(l.text.strip()) for l in body.lines)
    if zeichen > PODCAST_MAX_CHARS:
        raise HTTPException(status_code=422, detail=t(
            "podcast.scriptTooLong", locale,
            chars=f"{zeichen:,}".replace(",", "."),
            maxChars=f"{PODCAST_MAX_CHARS:,}".replace(",", ".")))

    params = store.load_params(job["user_id"], job_uuid)
    personen = len(params.persons) if params else 1
    sauber: list[Line] = []
    for line in body.lines:
        # A contribution just added is still empty, only the voicing insists on text.
        text = line.text.strip()[:PODCAST_MAX_LINE_CHARS]
        sprecher = line.speaker if 0 <= line.speaker < personen else 0
        sauber.append(Line(id=line.id, speaker=sprecher, text=text))
    if not sauber:
        raise HTTPException(status_code=422, detail=t("podcast.emptyScript", locale))

    sauber = store.next_ids(sauber)
    store.save_user_script(job["user_id"], job_uuid, sauber)
    return {"lines": [l.model_dump() for l in sauber]}
