"""Shared helpers für Screencast-Tasks: Cancel-Check, TTS-Client, Service-Resolver."""

from loguru import logger

from src.storage import get_job_file


class _JobCancelled(Exception):
    """Raised when the user clicked Abbrechen (Redis cancel flag is set)."""


def _assert_not_cancelled(job_uuid: str) -> None:
    """Raise _JobCancelled if a Redis cancel flag exists for this job."""
    cancelled = False
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        cancelled = bool(_r.exists(f"job:cancel:{job_uuid}"))
    except Exception as e:
        logger.warning("Cancel check Redis error: {}", e)
    if cancelled:
        logger.info("Job {} cancelled - killing active procs", job_uuid[:8])
        try:
            from src.services.screencast import kill_job_procs
            kill_job_procs(job_uuid)
        except Exception as e:
            logger.warning("kill_job_procs error: {}", e)
        raise _JobCancelled()


def _get_screencast_helpers():
    """Import screencast helpers lazily to avoid circular imports."""
    from src.services.screencast import (
        IMAGE_TMP_DIR,
        apply_faststart,
        concatenate_videos,
        convert_slides_to_images_async,
        create_outro_image,
        create_slide_video,
        extract_text_per_slide,
        generate_all_tts,
        get_image_dimensions,
        pptx_to_images,
    )
    return (
        IMAGE_TMP_DIR,
        pptx_to_images, generate_all_tts, convert_slides_to_images_async,
        create_slide_video, concatenate_videos, apply_faststart,
        extract_text_per_slide,
        create_outro_image, get_image_dimensions,
    )


def _get_tts_client(provider_id: int):
    from src.dependencies import get_tts_client_for_provider
    client = get_tts_client_for_provider(provider_id)
    if client is None:
        raise RuntimeError(f"TTS-Provider {provider_id} nicht gefunden oder deaktiviert")
    if not client.is_available():
        raise RuntimeError(f"TTS-Provider {provider_id} nicht erreichbar")
    return client


def _get_pptx_for_render(user_id: int, save_uuid: str) -> bytes:
    """Get PPTX for rendering: corrected version if available, else translated."""
    try:
        return get_job_file(user_id, save_uuid, "corrected.pptx")
    except Exception:
        pass
    return get_job_file(user_id, save_uuid, "translated.pptx")
