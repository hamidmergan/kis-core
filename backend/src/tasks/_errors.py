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


def handle_task_exception(job_uuid: str, e: Exception, *, task_label: str) -> None:
    """Common error path: localize FeatureNotConfigured, pass anything else
    through as ``str(e)``. Always writes ``job_status=failed`` so the caller
    just needs to ``raise`` after to surface the exception to Celery."""
    from src.services.feature_router import FeatureNotConfigured

    if isinstance(e, FeatureNotConfigured):
        msg = t("job.featureNotConfigured", job_locale(job_uuid))
    else:
        msg = str(e)
    logger.error("{} task {} failed: {}", task_label, job_uuid, e)
    db.update_job_status(job_uuid, "failed", error_message=msg)
