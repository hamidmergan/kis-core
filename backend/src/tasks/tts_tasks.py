"""Celery task: Text-to-Speech synthesis."""

from pathlib import Path

import httpx
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import delete_file, get_file, get_job_file, save_job_file, save_result_file
from src.utils.heartbeat import job_heartbeat


@celery_app.task(bind=True, name="tts.run", queue="tts", acks_late=True, max_retries=7)
def run_tts(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    stability: float,
    similarity_boost: float,
    style: float,
    use_speaker_boost: bool,
    pause_preset: str,
):
    """Synthesize uploaded document to MP3 via ElevenLabs.

    Long texts are split into ≤25k-char chunks. Each chunk is saved immediately
    after synthesis so a crash or network error can be resumed without re-paying
    for already completed chunks.
    """
    try:
        # Save params so the job can be manually retried later via POST /jobs/{uuid}/retry
        tts_params = {
            "voice_id": voice_id, "speed": speed, "stability": stability,
            "similarity_boost": similarity_boost, "style": style,
            "use_speaker_boost": use_speaker_boost, "pause_preset": pause_preset,
        }
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

        from src.services.elevenlabs_client import ElevenLabsClient, _split_text, _insert_pauses
        from src.config import Settings
        api_key = Settings().elevenlabs_api_key
        if not api_key:
            raise RuntimeError("ElevenLabs API Key nicht konfiguriert")

        client = ElevenLabsClient(api_key)
        chunks = _split_text(_insert_pauses(text, pause_preset))
        n = len(chunks)

        audio_parts: list[bytes] = []
        prev_text = ""

        for i, chunk in enumerate(chunks):
            chunk_filename = f"chunk_{i:03d}.mp3"

            # Resume: skip chunks already synthesized in a previous (crashed) run
            try:
                existing = get_job_file(job_uuid, chunk_filename)
                audio_parts.append(existing)
                prev_text = chunk
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
                    stability=stability,
                    similarity_boost=similarity_boost,
                    style=style,
                    use_speaker_boost=use_speaker_boost,
                    previous_text=prev_text,
                )

            save_job_file(job_uuid, chunk_filename, mp3)
            audio_parts.append(mp3)
            prev_text = chunk

        # Combine all chunks and save final result
        result_path = save_result_file(job_uuid, ".mp3", b"".join(audio_parts))
        result_filename = f"{Path(filename).stem}.mp3"
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        delete_file(input_path)

        logger.info("TTS task {} completed: {} ({} chunk(s))", job_uuid, result_filename, n)

    except (httpx.NetworkError, httpx.TimeoutException) as e:
        if self.request.retries < self.max_retries:
            wait = min(30 * (2 ** self.request.retries), 3600)
            logger.warning("TTS {} network error, retry {}/{} in {}s: {}", job_uuid, self.request.retries + 1, self.max_retries, wait, e)
            raise self.retry(exc=e, countdown=wait)
        logger.error("TTS {} gave up after {} retries: {}", job_uuid, self.max_retries, e)
        db.update_job_status(job_uuid, "failed", error_message="ElevenLabs war ~90 Minuten nicht erreichbar. Bitte 'Wiederholen' klicken wenn der Dienst wieder verfügbar ist.")
        raise

    except Exception as e:
        logger.error("TTS task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
