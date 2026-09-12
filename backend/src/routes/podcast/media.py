"""Listening to a single contribution while the rest is still being voiced."""

import re

from fastapi import APIRouter, Depends, HTTPException, Response

from src.dependencies import get_current_user
from src.features.podcast import store
from src.i18n import get_locale, t
from src.routes.podcast._shared import own_job

router = APIRouter(tags=["podcast"])

_LINE_ID = re.compile(r"^b[0-9]{1,4}$")


@router.get("/podcast/{job_uuid}/line/{line_id}")
async def get_line_audio(
    job_uuid: str,
    line_id: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """One contribution as MP3, only for the person the job belongs to."""
    job = own_job(job_uuid, current_user, locale)
    if not _LINE_ID.match(line_id):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    ton = store.get_line_audio(job["user_id"], job_uuid, line_id)
    if ton is None:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    # The audio changes with the text, so the browser must not keep it.
    return Response(content=ton, media_type="audio/mpeg",
                    headers={"Cache-Control": "no-store"})


@router.get("/podcast/{job_uuid}/transcript")
async def get_transcript(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The whole conversation as text, names in front of every contribution."""
    job = own_job(job_uuid, current_user, locale)
    zeilen = store.load_lines(job["user_id"], job_uuid)
    params = store.load_params(job["user_id"], job_uuid)
    if not zeilen or not params:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    namen = [params.persons[l.speaker].name if l.speaker < len(params.persons)
             else params.persons[0].name for l in zeilen]
    text = "\n\n".join(f"{n}: {l.text}" for n, l in zip(namen, zeilen)) + "\n"
    return Response(content=text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="podcast.txt"'})
