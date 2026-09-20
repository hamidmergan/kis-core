"""The one failure path of a long job: resume by itself a few times, then pause and wait."""

from __future__ import annotations

import json

from loguru import logger

from src import database as db
from src.i18n import t
from src.limits import MAX_AUTO_RESUMES, RETRY_BACKOFF_SECONDS

_SCREENCAST_TOOLS = ("screencast_translate", "screencast_render")


def resume_entry(job: dict) -> str | None:
    """Which door a job goes back in through, None when it cannot be resumed at all."""
    tool = job.get("tool") or ""
    if tool in _SCREENCAST_TOOLS:
        return "screencast"
    if tool == "tts":
        return "tts"
    if tool == "podcast":
        # Only the voicing keeps its finished parts, a half written script is worth nothing.
        return None if _progress(job).get("step") == "script" else "podcast"
    if tool == "summary":
        return "summary"
    if tool == "praesentation":
        # Only the build keeps finished texts and pictures, a half written outline is worth nothing.
        return None if _progress(job).get("step") in ("outline", "outline_done") else "praesentation"
    return None


def _progress(job: dict) -> dict:
    roh = job.get("progress")
    if isinstance(roh, dict):
        return roh
    try:
        return json.loads(roh) if roh else {}
    except (TypeError, ValueError):
        return {}


def attempt_failed(job_uuid: str, message: str, *, stale_before=None) -> str | None:
    """Counts one failed attempt, returns the new status or None when it no longer applied."""
    job = db.get_job(job_uuid)
    if not job:
        return None
    if resume_entry(job) is None:
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


def still_mine(job_uuid: str, token: int) -> bool:
    """False when the job was parked, cancelled or handed to a newer run in the meantime."""
    stand = db.job_claim(job_uuid)
    return bool(stand and stand[0] in ("pending", "running") and stand[1] == token)


def resume_due_jobs() -> int:
    """Starts every job whose next try is due, one supervisor duty of the watchdog."""
    faellig = db.claim_due_retries()
    for job in faellig:
        try:
            dispatch_resume(job)
        except Exception as e:  # noqa: BLE001 - a failed dispatch is just the next failed attempt
            logger.error("Job {}: Wiederanlauf nicht absendbar: {}", job["job_uuid"][:8], e)
            attempt_failed(job["job_uuid"], str(e))
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
            args=[job_uuid, user_id, job.get("creator_locale") or "de", 1, job["attempts"]])
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "tts":
        from src.tasks.tts_tasks import run_tts

        params = _tts_params(job)
        task = run_tts.apply_async(args=[
            job_uuid, job["input_path"], job["original_filename"],
            params["voice_id"], params["speed"], params["provider_id"],
            params.get("voice_label", ""), job["attempts"],
        ])
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "screencast":
        from src.tasks.screencast_tasks._queue import dispatch_next_screencast_job_for_user

        dispatch_next_screencast_job_for_user(user_id)
    elif tuer == "summary":
        from src.tasks.summary_tasks import run_summary

        params = _summary_params(job)
        task = run_summary.apply_async(args=[
            job_uuid, params["sources"], params["template_slug"],
            params.get("provider_id"), job["attempts"],
        ])
        db.set_job_celery_task_id(job_uuid, task.id)
    elif tuer == "praesentation":
        from src.tasks.podcast_tasks._shared import clear_cancel
        from src.tasks.praesentation_tasks import run_praesentation_build

        clear_cancel(job_uuid)
        # A finalize parked mid-run must resume as a finalize, or the download never opens.
        final = bool(_progress(job).get("final"))
        task = run_praesentation_build.apply_async(
            args=[job_uuid, user_id, job.get("creator_locale") or "de", 1, job["attempts"], None, final])
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


def _summary_params(job: dict) -> dict:
    """The sources and the build plan of that run, kept in the job folder."""
    from src.storage import get_job_file

    try:
        return json.loads(get_job_file(job["user_id"], job["job_uuid"], "summary_params.json"))
    except Exception as e:  # noqa: BLE001 - without them there is nothing left to resume
        raise RuntimeError("Angaben dieses Auftrags sind nicht mehr da") from e
