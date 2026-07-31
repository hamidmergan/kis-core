"""Shared Celery task error-handling.

Centralises two patterns every general/TTS/translate/transcribe task needs:

  - Recovering the creator's UI locale off the job row (Celery workers have
    no HTTP context, so we can't use ``Depends(get_locale)``).
  - Detecting ``FeatureNotConfigured`` from the feature_router and turning
    it into a localized "feature not configured" message — instead of
    leaking the internal English exception text into the job log.
"""

from __future__ import annotations

from loguru import logger

from src import database as db
from src.i18n import t


def job_locale(job_uuid: str) -> str:
    """Read the creator's UI locale off the job row, default to 'de'."""
    job = db.get_job(job_uuid)
    return (job and job.get("creator_locale")) or "de"


def audio_too_long_message(e, locale: str) -> str:
    """Wording for :class:`AudioTooLongError`, shared by the transcription tool
    and KI-Tutor media ingestion so both say the same thing in both languages."""
    return t(
        "transcription.audioTooLong",
        locale,
        minutes=f"{e.duration_sec / 60:.0f}",
        maxMinutes=e.max_sec // 60,
    )


def handle_task_exception(job_uuid: str, e: Exception, *, task_label: str) -> None:
    """Common error path: localize the errors a user can act on, pass anything
    else through as ``str(e)``. Always writes ``job_status=failed`` so the caller
    just needs to ``raise`` after to surface the exception to Celery.

    Localizing here rather than at the raise site is deliberate: only the job row
    knows which language its creator uses (Celery workers have no HTTP context).
    """
    from src.services.feature_router import FeatureNotConfigured
    from src.services.openai_compat_llm._chunking import AudioTooLongError

    if isinstance(e, FeatureNotConfigured):
        msg = t("job.featureNotConfigured", job_locale(job_uuid))
    elif isinstance(e, AudioTooLongError):
        msg = audio_too_long_message(e, job_locale(job_uuid))
    else:
        msg = str(e)
    logger.error("{} task {} failed: {}", task_label, job_uuid, e)
    db.update_job_status(job_uuid, "failed", error_message=msg)
