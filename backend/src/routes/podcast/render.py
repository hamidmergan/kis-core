"""Starting the voicing, again after a failure or a change."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.features.podcast import store
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.routes.podcast._shared import own_job
from src.security.rate_limit import enforce_tool_burst

router = APIRouter(tags=["podcast"])

_STARTBAR = ("awaiting_user", "failed", "success")


@router.post("/podcast/{job_uuid}/render")
async def start_render(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Voices what is open, a second run skips everything unchanged."""
    job = own_job(job_uuid, current_user, locale)
    user_id = job["user_id"]
    if job["status"] not in _STARTBAR:
        raise HTTPException(status_code=409, detail=t("podcast.running", locale))
    if not store.load_lines(user_id, job_uuid):
        raise HTTPException(status_code=422, detail=t("podcast.emptyScript", locale))

    enforce_tool_burst(user_id, "podcast", locale)
    enforce_quota(user_id, "podcast", is_admin_user(current_user), locale)

    from src.tasks.podcast_tasks import run_podcast_render

    task = run_podcast_render.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "tts"})
    logger.info("Podcast {}: Vertonung gestartet", job_uuid[:8])
    return {"job_uuid": job_uuid}
