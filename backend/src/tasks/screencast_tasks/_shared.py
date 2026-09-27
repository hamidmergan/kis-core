"""Shared helpers for screencast tasks: cancel check, TTS client, service resolver."""

import json
import os
from loguru import logger

from src.services import tts_job_provider
from src.storage import get_job_file, is_missing, save_job_file


class _JobCancelled(Exception):
    """Raised when the user clicked Abbrechen (Redis cancel flag is set)."""


def _assert_not_cancelled(job_uuid: str) -> None:
    """Raise _JobCancelled if a Redis cancel flag exists for this job."""
    cancelled = False
    try:
        import redis as _redis
        _r = _redis.from_url(os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"))
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


def _stimme_festlegen(user_id: int, job_uuid: str, provider_id: int, voice_id: str, voice_label: str) -> dict:
    """The provider and voice the whole run speaks with, decided on its first run and read back ever after."""
    try:
        params = json.loads(get_job_file(user_id, job_uuid, "queue_params.json"))
    except Exception as e:
        # Only a missing file means no pin, any other failure must not decide the voice anew.
        if not is_missing(e):
            raise
        params = {}
    pin = params.get("tts_pin")
    if isinstance(pin, dict):
        return pin
    wahl = tts_job_provider.pick(provider_id, [voice_id])
    stimme = wahl.voices[0]
    pin = {
        "provider_id": wahl.provider_id,
        "voice_id": stimme,
        "voice_label": tts_job_provider.voice_name(wahl.provider_id, stimme) if wahl.fallback else voice_label,
        "fallback": wahl.fallback,
        "requested_provider_id": provider_id,
        "requested_voice_id": voice_id,
    }
    # Resume and the queue read this file, so they start the same run with the same voice.
    params.update(tts_pin=pin, provider_id=pin["provider_id"], voice_id=pin["voice_id"], voice_label=pin["voice_label"])
    save_job_file(user_id, job_uuid, "queue_params.json", json.dumps(params).encode())
    return pin


def _get_pptx_for_render(user_id: int, save_uuid: str) -> bytes:
    """Get PPTX for rendering: corrected version if available, else translated."""
    try:
        return get_job_file(user_id, save_uuid, "corrected.pptx")
    except Exception:
        pass
    return get_job_file(user_id, save_uuid, "translated.pptx")
