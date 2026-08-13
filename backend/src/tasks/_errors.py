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


# Meldungen, hinter denen der Dienst des Anbieters steckt und nicht die Eingabe
# der Nutzerin. Roh sahen die im Bildschirm so aus:
#   TTS API error (500): Internal Server Error
# Damit kann niemand etwas anfangen, und zu tun ist ohnehin nur eines, spaeter
# noch einmal versuchen. 500 gehoert ausdruecklich dazu, myLab beendet damit
# jede Anfrage, die ihm zu lange dauert.
_BUSY_MARKERS = (
    "429", "rate limit", "too many requests",
    "500", "internal server error",
    "502", "503", "504",
    "bad gateway", "service unavailable", "gateway timeout",
    "timeout", "timed out",
)


def is_upstream_busy(e: Exception | str) -> bool:
    """Wahr, wenn der Anbieter ueberlastet war oder nicht geantwortet hat.

    Ueber den Text und nicht ueber den Typ, weil die Werkzeuge ihre Fehler aus
    drei Ecken bekommen (httpx, openai, eigene RuntimeError) und der Status nur
    im Text steht. Nimmt auch den fertigen Text, der Screencast reicht das
    ``detail`` einer HTTPException herein.
    """
    msg = str(e).lower()
    return any(m in msg for m in _BUSY_MARKERS)


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
    elif is_upstream_busy(e):
        msg = t("job.upstreamBusy", job_locale(job_uuid))
    else:
        msg = str(e)
    logger.error("{} task {} failed: {}", task_label, job_uuid, e)
    db.update_job_status(job_uuid, "failed", error_message=msg)
