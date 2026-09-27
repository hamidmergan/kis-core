"""Celery task: Text-to-Speech synthesis."""

import json
import subprocess
import tempfile
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.services.ai_hinweis import ffmpeg_metadata_args
from src.services.job_recovery import _progress, attempt_failed, still_mine
from src.services.tts_job_provider import pick, voice_name
from src.storage import (
    delete_file, get_file, get_job_file, is_missing, job_file_exists, save_job_file, save_result_file,
    save_result_and_evict,
)
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT


def _pinned_params(user_id: int, job_uuid: str, voice_id: str, voice_label: str, speed: float,
                   provider_id: int, progress: dict) -> dict:
    """The provider and voice the whole job speaks with, decided once at its first real run."""
    try:
        stored = json.loads(get_job_file(user_id, job_uuid, "tts_params.json"))
    except Exception as exc:  # noqa: BLE001 - only a missing file means no pin in the folder
        # Any other failure fails the stage, so a later resume still finds the pin.
        if not is_missing(exc):
            raise
        stored = {}
    if stored.get("pinned"):
        return stored
    # A pin the folder lost still rides in the progress and is laid down again.
    params = progress.get("tts_params") or {}
    if not params.get("pinned"):
        params = {"voice_id": voice_id, "voice_label": voice_label, "speed": speed, "provider_id": provider_id,
                  "requested_provider_id": provider_id, "fallback": False, "pinned": True}
        # Parts spoken by an older run keep their voice, one file never mixes two voices.
        if not job_file_exists(user_id, job_uuid, "chunk_000.mp3"):
            wahl = pick(provider_id, [voice_id])
            if wahl.fallback:
                params.update(provider_id=wahl.provider_id, voice_id=wahl.voices[0],
                              voice_label=voice_name(wahl.provider_id, wahl.voices[0]), fallback=True)
    # In the folder, not only in the progress: the next status write wipes the progress.
    save_job_file(user_id, job_uuid, "tts_params.json", json.dumps(params).encode())
    return params


def _stamped_with_ai_notice(mp3_bytes: bytes) -> bytes:
    """Remux the joined MP3 once, lossless, to stamp the AI notice into its metadata."""
    with tempfile.TemporaryDirectory(prefix="tts_notice_") as tmpdir:
        source = Path(tmpdir) / "raw.mp3"
        target = Path(tmpdir) / "stamped.mp3"
        source.write_bytes(mp3_bytes)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-c", "copy", *ffmpeg_metadata_args(), str(target)],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("TTS metadata stamp failed (rc={}): {}", result.returncode, result.stderr[-300:])
            return mp3_bytes
        return target.read_bytes()


@celery_app.task(
    bind=True,
    name="tts.run",
    queue="tts",
    acks_late=True,
    soft_time_limit=STAGE_SOFT_TIME_LIMIT,
    time_limit=STAGE_TIME_LIMIT,
)
def run_tts(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    provider_id: int,
    voice_label: str = "",
    versuch: int = 0,
):
    """Voices an uploaded document, every part is saved right away."""
    try:
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        clock = StageClock()
        job_row = db.get_job(job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {job_uuid} not found")
        user_id = job_row["user_id"]
        tts_params = _pinned_params(user_id, job_uuid, voice_id, voice_label, speed, provider_id, _progress(job_row))
        voice_id, voice_label, provider_id = tts_params["voice_id"], tts_params["voice_label"], tts_params["provider_id"]
        speed = tts_params.get("speed", speed)
        db.update_job_status(job_uuid, "running", progress={"step": "extract", "tts_params": tts_params})

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.utils.text_extraction import EXTRACTORS
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise ValueError(f"Unsupported file type: {ext}")

        text = extractor(content)
        if not text.strip():
            raise ValueError("Kein Text in der Datei gefunden")

        from src.dependencies import get_tts_client_for_provider, _voice_language_for
        from src.services.openai_compat_tts import _split_text

        client = get_tts_client_for_provider(provider_id)
        if client is None:
            raise RuntimeError(f"TTS-Provider {provider_id} nicht verfügbar.")

        # Derive language from DB — needed by some providers for phonemizer config
        language = _voice_language_for(provider_id, voice_id) or "de"

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

            # The stage did its share, the rest belongs to the next one.
            if clock.over():
                raise StageContinue
            if not still_mine(job_uuid, versuch):
                raise StageLost(job_uuid)

            db.update_job_status(job_uuid, "running", progress={
                "step": "synthesize", "chunk": i + 1, "total": n, "tts_params": tts_params})

            mp3 = client.synthesize_chunk(
                chunk,
                voice_id=voice_id,
                speed=speed,
                language=language,
            )

            save_job_file(user_id, job_uuid, chunk_filename, mp3)
            audio_parts.append(mp3)
            # A finished piece is the liveness sign, no clock thread ticks for us.
            db.touch_job_heartbeat(job_uuid)

        result_path = save_result_file(user_id, job_uuid, ".mp3", _stamped_with_ai_notice(b"".join(audio_parts)))
        result_filename = f"{Path(filename).stem}.mp3"
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        delete_file(input_path)

        logger.info("TTS task {} completed: {} ({} chunk(s))", job_uuid, result_filename, n)

    except StageContinue:
        continue_stage(self, [job_uuid, input_path, filename, voice_id, speed,
                              provider_id, voice_label, versuch], job_uuid)
        return
    except StageLost:
        logger.info("TTS {}: Etappe gehoert nicht mehr uns, nichts getan", job_uuid)
        return
    except Exception as e:
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(e, SoftTimeLimitExceeded):
            logger.warning("TTS task {} hit soft time limit", job_uuid)
            job = db.get_job(job_uuid)
            locale = (job and job.get("creator_locale")) or "de"
            attempt_failed(job_uuid, t("job.timeoutRetry", locale))
            return
        from src.tasks._errors import handle_task_exception
        handle_task_exception(job_uuid, e, task_label="TTS")
        raise
