"""The one failure path of a long job: resume by itself a few times, then pause and wait."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from loguru import logger

from src import database as db
from src.i18n import t
from src.services.upstream_errors import is_provider_refusal
from src.limits import (
    CONTINUED_PRIORITY, MAX_AUTO_RESUMES, PROVIDER_BUSY_MAX_HOURS, PROVIDER_BUSY_WAIT_SECONDS,
    RETRY_BACKOFF_SECONDS,
)

_SCREENCAST_TOOLS = ("screencast_translate", "screencast_render")


def resume_entry(job: dict) -> str | None:
    """Which door a job goes back in through, None when it cannot be resumed at all."""
    tool = job.get("tool") or ""
    if tool in _SCREENCAST_TOOLS:
        return "screencast"
    if tool == "tts":
        return "tts"
    if tool == "podcast":
        # The script starts over as a whole, only the voicing keeps its finished parts.
        return "podcast_script" if _progress(job).get("step") == "script" else "podcast"
    if tool == "summary":
        return "summary"
    if tool == "pages":
        return "pages"
    if tool == "praesentation":
        schritt = _progress(job).get("step")
        # The outline starts over as a whole, only the build keeps finished texts and pictures.
        return "praesentation_outline" if schritt in ("outline", "outline_done") else "praesentation"
    return None


# These steps only wait out an overloaded provider, any other failure ends them as before.
_NUR_BEI_UEBERLAST = {"podcast_script", "praesentation_outline"}


def _progress(job: dict) -> dict:
    roh = job.get("progress")
    if isinstance(roh, dict):
        return roh
    try:
        return json.loads(roh) if roh else {}
    except (TypeError, ValueError):
        return {}


def attempt_failed(job_uuid: str, message: str, *, stale_before=None, busy: bool = False,
                   refused: bool = False) -> str | None:
    """Counts one failed attempt, returns the new status or None when it no longer applied."""
    job = db.get_job(job_uuid)
    if not job:
        return None
    if refused and job.get("status") not in ("pending", "running", "waiting_retry"):
        return None
    tuer = resume_entry(job)
    # A provider that refused the call refuses the next one as well, so the job ends now.
    if tuer is None or refused:
        db.update_job_status(job_uuid, "failed", error_message=message)
        return "failed"
    if busy and not _busy_too_long(job):
        # A full provider says nothing about the job, it waits in line again uncounted.
        return db.record_busy_wait(job_uuid, message, wait_seconds=random.uniform(*PROVIDER_BUSY_WAIT_SECONDS))
    if tuer in _NUR_BEI_UEBERLAST:
        db.update_job_status(job_uuid, "failed", error_message=message)
        return "failed"
    locale = job.get("creator_locale") or "de"
    status = db.record_failed_attempt(
        job_uuid, message,
        max_resumes=MAX_AUTO_RESUMES,
        backoff=RETRY_BACKOFF_SECONDS,
        paused_message=t("job.pausedAfterAttempts", locale, n=MAX_AUTO_RESUMES, error=message),
        stale_before=stale_before,
    )
    if status:
        logger.info("Job {}: Anlauf gescheitert, jetzt {}", job_uuid[:8], status)
    return status


def _busy_too_long(job: dict) -> bool:
    """True once a job has existed longer than a full provider may hold it up."""
    erstellt = job.get("created_at")
    if not isinstance(erstellt, datetime):
        return False
    if erstellt.tzinfo is None:
        erstellt = erstellt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - erstellt > timedelta(hours=PROVIDER_BUSY_MAX_HOURS)


def still_mine(job_uuid: str, token: int) -> bool:
    """False when the job was parked, cancelled or handed to a newer run in the meantime."""
    stand = db.job_claim(job_uuid)
    mine = bool(stand and stand[0] in ("pending", "running") and stand[1] == token)
    if mine:
        # A stage fetched after a long wait reports in at once, before its first unit.
        db.touch_job_heartbeat(job_uuid)
    return mine


def resume_due_jobs() -> int:
    """Starts every job whose next try is due, one supervisor duty of the watchdog."""
    faellig = db.claim_due_retries()
    for job in faellig:
        try:
            dispatch_resume(job)
        except Exception as e:  # noqa: BLE001 - a failed dispatch is just the next failed attempt
            logger.error("Job {}: Wiederanlauf nicht absendbar: {}", job["job_uuid"][:8], e)
            attempt_failed(job["job_uuid"], str(e), refused=is_provider_refusal(e))
    return len(faellig)


def dispatch_resume(job: dict) -> None:
    """Hands the job back to its tool, on the same job_uuid so finished units are skipped."""
    job_uuid, user_id = job["job_uuid"], job["user_id"]
    tuer = resume_entry(job)
    if tuer == "podcast":
        from src.tasks.podcast_tasks import run_podcast_render
        from src.tasks.podcast_tasks._shared import clear_cancel

        clear_cancel(job_uuid)
        task = run_podcast_render.apply_async(
            args=[job_uuid, user_id, job.get("creator_locale") or "de", 1, job["attempts"]], priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer in ("podcast_script", "praesentation_outline"):
        from src.tasks.podcast_tasks._shared import clear_cancel

        clear_cancel(job_uuid)
        if tuer == "podcast_script":
            from src.tasks.podcast_tasks import run_podcast_script as task_fn
        else:
            from src.tasks.praesentation_tasks import run_praesentation_outline as task_fn
        task = task_fn.apply_async(
            args=[job_uuid, user_id, job.get("creator_locale") or "de", 1, job["attempts"]], priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "tts":
        from src.tasks.tts_tasks import run_tts

        params = _tts_params(job)
        task = run_tts.apply_async(args=[
            job_uuid, job["input_path"], job["original_filename"],
            params["voice_id"], params["speed"], params["provider_id"],
            params.get("voice_label", ""), job["attempts"],
        ], priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "screencast":
        from src.tasks.screencast_tasks._queue import dispatch_next_screencast_job_for_user

        dispatch_next_screencast_job_for_user(user_id)
    elif tuer == "summary":
        from src.tasks.summary_tasks import run_summary

        params = _summary_params(job)
        task = run_summary.apply_async(args=[
            job_uuid, params["template_slug"], params.get("provider_id"), job["attempts"],
        ], priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "pages":
        from src.tasks.pages_tasks import run_pages

        params = _pages_params(job)
        task = run_pages.apply_async(args=[job_uuid, params.get("provider_id"), job["attempts"]],
                                     priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "praesentation":
        from src.tasks.podcast_tasks._shared import clear_cancel
        from src.tasks.praesentation_tasks import run_praesentation_build

        clear_cancel(job_uuid)
        # A finalize parked mid-run must resume as a finalize, or the download never opens.
        final = bool(_progress(job).get("final"))
        task = run_praesentation_build.apply_async(
            args=[job_uuid, user_id, job.get("creator_locale") or "de", 1, job["attempts"], None, final],
            priority=CONTINUED_PRIORITY)
        db.set_job_celery_task_id(job_uuid, task.id)
    else:
        raise RuntimeError(f"Kein Wiederanlauf fuer Dienst {job.get('tool')}")


def _tts_params(job: dict) -> dict:
    """The voice settings of that run, from the job folder and from the progress as a fallback."""
    from src.storage import get_job_file

    try:
        return json.loads(get_job_file(job["user_id"], job["job_uuid"], "tts_params.json"))
    except Exception:  # noqa: BLE001 - older jobs only carry them in the progress
        params = _progress(job).get("tts_params")
        if not params:
            raise RuntimeError("Stimm-Einstellungen dieses Auftrags sind nicht mehr da") from None
        return params


def recover_after_restart() -> int:
    """Jobs that were mid-run when the broker was lost, handed to the resume path."""
    offen = db.jobs_in_flight()
    for job in offen:
        locale = job.get("creator_locale") or "de"
        meldung = t("job.serverRestarted", locale)
        if resume_entry(job) is None:
            db.update_job_status(job["job_uuid"], "failed", error_message=meldung)
        else:
            # Due right away, the supervisor picks it up on its next tick.
            db.record_failed_attempt(
                job["job_uuid"], meldung,
                max_resumes=MAX_AUTO_RESUMES, backoff=(0, 0, 0),
            )
    return len(offen)


def _pages_params(job: dict) -> dict:
    """The provider of that page's run, an empty choice when the file is gone."""
    from src.storage import get_job_file

    try:
        return json.loads(get_job_file(job["user_id"], job["job_uuid"], "pages_params.json"))
    except Exception:  # noqa: BLE001 - the default provider takes over
        return {}


def _summary_params(job: dict) -> dict:
    """The build plan and the provider of that run, kept in the job folder."""
    from src.storage import get_job_file

    try:
        return json.loads(get_job_file(job["user_id"], job["job_uuid"], "summary_params.json"))
    except Exception as e:  # noqa: BLE001 - without them there is nothing left to resume
        raise RuntimeError("Angaben dieses Auftrags sind nicht mehr da") from e
