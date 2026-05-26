"""Celery task: Text-to-Speech synthesis."""

from pathlib import Path

import httpx
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.storage import delete_file, get_file, get_job_file, save_job_file, save_result_file, save_result_and_evict
from src.utils.heartbeat import job_heartbeat
from src.limits import TTS_SOFT_TIME_LIMIT, TTS_TIME_LIMIT


@celery_app.task(
    bind=True,
    name="tts.run",
    queue="tts",
    acks_late=True,
    max_retries=7,
    soft_time_limit=TTS_SOFT_TIME_LIMIT,
    time_limit=TTS_TIME_LIMIT,
)
def run_tts(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    provider: str = "kokoro",
    voice_label: str = "",
):
    """Synthesize uploaded document to MP3.

    Long texts are split into ≤25k-char chunks. Each chunk is saved immediately
    after synthesis so a crash or network error can be resumed without re-paying
    for already completed chunks.
    """
    try:
        # Save params so the job can be manually retried later via POST /jobs/{uuid}/retry
        tts_params = {
            "voice_id": voice_id, "voice_label": voice_label, "speed": speed,
            "provider": provider,
        }
        db.update_job_status(job_uuid, "running", progress={"step": "extract", "tts_params": tts_params})
        job_row = db.get_job(job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {job_uuid} not found")
        user_id = job_row["user_id"]

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.utils.text_extraction import EXTRACTORS
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise ValueError(f"Unsupported file type: {ext}")

        text = extractor(content)
        if not text.strip():
            raise ValueError("Kein Text in der Datei gefunden")

        from src.dependencies import (
            get_kokoro_client, get_mylab_client,
            is_kokoro_enabled, is_mylab_enabled,
        )

        requested_provider = tts_params.get("provider", "kokoro")

        # Hard-stop: reject if provider was disabled / unconfigured between
        # submit and execution. Both helpers now read the providers table via
        # feature_router, so an unconfigured TTS route fails loudly here.
        if requested_provider == "mylab":
            if not is_mylab_enabled():
                raise RuntimeError("myLab TTS wurde deaktiviert.")
            client = get_mylab_client()
            if client is None:
                raise RuntimeError("myLab TTS-Anbieter nicht verfügbar.")
            from src.services.openai_compat_tts import _split_text
        else:
            if not is_kokoro_enabled():
                raise RuntimeError("Kokoro TTS wurde deaktiviert.")
            client = get_kokoro_client()
            if client is None:
                raise RuntimeError("Kokoro TTS-Anbieter nicht verfügbar.")
            from src.services.kokoro_client import _split_text
        chunks = _split_text(text)
        n = len(chunks)

        audio_parts: list[bytes] = []

        for i, chunk in enumerate(chunks):
            chunk_filename = f"chunk_{i:03d}.mp3"

            # Resume: skip chunks already synthesized in a previous (crashed) run
            try:
                existing = get_job_file(user_id, job_uuid, chunk_filename)
                audio_parts.append(existing)
                logger.info("TTS {}: chunk {}/{} already saved, skipping", job_uuid, i + 1, n)
                continue
            except Exception:
                pass

            db.update_job_status(job_uuid, "running", progress={"step": "synthesize", "chunk": i + 1, "total": n})

            with job_heartbeat(job_uuid):
                mp3 = client.synthesize_chunk(
                    chunk,
                    voice_id=voice_id,
                    speed=speed,
                )

            save_job_file(user_id, job_uuid, chunk_filename, mp3)
            audio_parts.append(mp3)

        # Combine all chunks and save final result
        result_path = save_result_file(user_id, job_uuid, ".mp3", b"".join(audio_parts))
        result_filename = f"{Path(filename).stem}.mp3"
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        delete_file(input_path)

        logger.info("TTS task {} completed: {} ({} chunk(s))", job_uuid, result_filename, n)

    except (httpx.NetworkError, httpx.TimeoutException) as e:
        if self.request.retries < self.max_retries:
            wait = min(30 * (2 ** self.request.retries), 3600)
            logger.warning("TTS {} network error, retry {}/{} in {}s: {}", job_uuid, self.request.retries + 1, self.max_retries, wait, e)
            raise self.retry(exc=e, countdown=wait)
        logger.error("TTS {} gave up after {} retries: {}", job_uuid, self.max_retries, e)
        provider_name = {"kokoro": "Kokoro", "mylab": "myLab TTS"}.get(provider, "Kokoro")
        job = db.get_job(job_uuid)
        locale = (job and job.get("creator_locale")) or "de"
        db.update_job_status(job_uuid, "failed", error_message=t("job.providerUnreachableRetry", locale, provider=provider_name))
        raise

    except Exception as e:
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(e, SoftTimeLimitExceeded):
            logger.warning("TTS task {} hit soft time limit", job_uuid)
            job = db.get_job(job_uuid)
            locale = (job and job.get("creator_locale")) or "de"
            db.update_job_status(job_uuid, "failed", error_message=t("job.timeoutRetry", locale))
            return  # exit cleanly before the hard SIGKILL fires
        from src.tasks._errors import handle_task_exception
        handle_task_exception(job_uuid, e, task_label="TTS")
        raise
