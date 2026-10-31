"""Shared error handling of the jobs, including the creator's language."""

from __future__ import annotations

from loguru import logger

from src import database as db
from src.i18n import t
# The check sits neutrally in services, here only its name.
from src.services.upstream_errors import is_provider_refusal, is_upstream_busy  # noqa: F401


def job_locale(job_uuid: str) -> str:
    """Read the creator's UI locale off the job row, default to 'de'."""
    job = db.get_job(job_uuid)
    return (job and job.get("creator_locale")) or "de"


def audio_too_long_message(e, locale: str) -> str:
    """The wording for an overlong recording, shared by both paths."""
    return t(
        "transcription.audioTooLong",
        locale,
        minutes=f"{e.duration_sec / 60:.0f}",
        maxMinutes=e.max_sec // 60,
    )


def window_too_small_message(e, locale: str) -> str:
    """The model's window and what the service needs, in the person's number format."""
    from src.limits import MAP_MIN_WINDOW_TOKENS

    def zahl(n) -> str:
        return f"{int(n):,}".replace(",", "." if locale == "de" else ",")

    fenster = e.args[0] if e.args else 0
    return t("job.modelWindowTooSmall", locale, window=zahl(fenster), min=zahl(MAP_MIN_WINDOW_TOKENS))


def handle_task_exception(job_uuid: str, e: Exception, *, task_label: str) -> None:
    """Translates the errors a user can act on, then fails or counts one attempt."""
    from src.services.feature_router import FeatureNotConfigured
    from src.services.openai_compat_llm._chunking import AudioTooLongError, NoAudioTrackError
    from src.services import job_recovery

    from src.services.own_tts._base import OwnInterfaceError
    from src.services.text_map import WindowTooSmall

    # Trying these again changes nothing, the input or the setup is wrong.
    dauerhaft = isinstance(e, (FeatureNotConfigured, AudioTooLongError, ValueError))
    if isinstance(e, OwnInterfaceError):
        # A wrong key or an empty balance of a person's own service, only the person can fix that.
        dauerhaft = e.permanent
        msg = e.message(job_locale(job_uuid))
    elif isinstance(e, FeatureNotConfigured):
        msg = t("job.featureNotConfigured", job_locale(job_uuid))
    elif isinstance(e, AudioTooLongError):
        msg = audio_too_long_message(e, job_locale(job_uuid))
    elif isinstance(e, NoAudioTrackError):
        msg = t("transcription.noAudioTrack", job_locale(job_uuid))
    elif isinstance(e, WindowTooSmall):
        msg = window_too_small_message(e, job_locale(job_uuid))
    elif is_provider_refusal(e):
        # Asking again gets the same no, the admin has to fix the provider.
        dauerhaft = True
        msg = t("job.providerRefused", job_locale(job_uuid))
    elif is_upstream_busy(e):
        msg = t("job.upstreamBusy", job_locale(job_uuid))
    else:
        msg = str(e)
    logger.error("{} task {} failed: {}", task_label, job_uuid, e)
    if dauerhaft:
        db.update_job_status(job_uuid, "failed", error_message=msg)
    else:
        job_recovery.attempt_failed(job_uuid, msg, busy=is_upstream_busy(e))
