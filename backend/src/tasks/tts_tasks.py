"""Celery task: Text-to-Speech synthesis."""

from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import save_queue_file, save_result_file


@celery_app.task(bind=True, name="tts.run")
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
    """Synthesize uploaded document to MP3 via ElevenLabs."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "extract"})

        content = Path(input_path).read_bytes()
        ext = Path(filename).suffix.lower()

        # Extract text from document
        from src.utils.text_extraction import EXTRACTORS
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise ValueError(f"Unsupported file type: {ext}")

        text = extractor(content)
        if not text.strip():
            raise ValueError("Kein Text in der Datei gefunden")

        db.update_job_status(job_uuid, "running", progress={"step": "synthesize"})

        # Synthesize
        from src.dependencies import get_settings
        from src.services.elevenlabs_client import ElevenLabsClient
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            raise RuntimeError("ElevenLabs API Key fehlt")

        client = ElevenLabsClient(settings.elevenlabs_api_key)
        mp3_bytes = client.synthesize(
            text,
            "EN",
            voice_id=voice_id,
            speed=speed,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost,
            pause_preset=pause_preset,
        )

        # Save result
        result_path = save_result_file(job_uuid, ".mp3", mp3_bytes)
        result_filename = f"{Path(filename).stem}_EN.mp3"
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        # Clean up input file
        Path(input_path).unlink(missing_ok=True)

        logger.info("TTS task {} completed: {}", job_uuid, result_filename)

    except Exception as e:
        logger.error("TTS task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
