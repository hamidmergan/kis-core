import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src.dependencies import get_elevenlabs_client, get_current_user
from src import database as db
from src.storage import save_queue_file
from src.services.elevenlabs_client import DEFAULT_VOICE_ID
from src.utils.file_validation import TTS_EXTENSIONS, MAX_UPLOAD_BYTES, TTS_MAX_CHARS
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["tts"])


# ---------- Routes ----------


_FALLBACK_VOICES = [
    {"voice_id": DEFAULT_VOICE_ID, "label": "Brian", "preview_url": None},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah", "preview_url": None},
]


@router.get("/voices")
async def list_voices():
    """Return available TTS voices from ElevenLabs (English premade only).

    Falls back to a hardcoded list of two voices if the API is unavailable.
    """
    from src.dependencies import get_settings
    import httpx

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        return {"voices": _FALLBACK_VOICES}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.elevenlabs_api_key},
            )
        if resp.status_code != 200:
            return {"voices": _FALLBACK_VOICES}

        all_voices = resp.json().get("voices", [])
        _NON_ENGLISH = {
            "german", "deutsch", "de",
            "french", "français", "fr",
            "spanish", "español", "es",
            "portuguese", "português", "pt",
            "italian", "italiano", "it",
            "dutch", "nl", "polish", "pl",
            "russian", "ru", "japanese", "ja",
            "chinese", "zh", "korean", "ko",
        }

        def _is_english(v: dict) -> bool:
            labels = v.get("labels") or {}
            language = labels.get("language", "").lower().strip()
            accent = labels.get("accent", "").lower().strip()
            return language not in _NON_ENGLISH and accent not in _NON_ENGLISH

        english_voices = [
            {
                "voice_id": v["voice_id"],
                "label": v["name"],
                "preview_url": v.get("preview_url"),
                "category": v.get("category"),
                "description": (v.get("labels") or {}).get("description"),
                "use_case": (v.get("labels") or {}).get("use_case"),
            }
            for v in all_voices
            if v.get("category") not in ("cloned", "generated")
            and _is_english(v)
        ]
        if not english_voices:
            return {"voices": _FALLBACK_VOICES}
        return {"voices": english_voices}
    except Exception:
        return {"voices": _FALLBACK_VOICES}


@router.post("/tts")
async def text_to_speech(
    request: Request,
    file: UploadFile = File(...),
    voice_id: str = Form(""),
    speed: float = Form(0.9),
    stability: float = Form(0.70),
    similarity_boost: float = Form(0.60),
    style: float = Form(0.20),
    use_speaker_boost: bool = Form(True),
    pause_preset: str = Form("medium"),
    current_user: dict = Depends(get_current_user),
):
    """Queue a TTS job: synthesize uploaded document to MP3 via ElevenLabs.

    Returns ``{ job_uuid }`` immediately. Poll ``GET /jobs/{job_uuid}`` for status.
    On success the result contains ``download_url`` for the MP3.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in TTS_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Nur .docx, .md oder .txt erlaubt"
        )

    valid_presets = {"short", "medium", "long", "very_long"}
    if pause_preset not in valid_presets:
        raise HTTPException(status_code=400, detail="Ungültiges Pausen-Preset")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    # Validate file type and that text can be extracted (fast check before queuing)
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")

    text = extractor(content)
    if len(text) > TTS_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Dokument zu lang ({len(text):,} Zeichen). Bitte aufteilen (max. {TTS_MAX_CHARS:,} Zeichen).".replace(",", "."),
        )

    # Validate ElevenLabs client is configured
    get_elevenlabs_client()

    user_id = current_user.get("user_id", 0)
    if db.has_active_job_for_tool(user_id, ["tts"]):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden TTS-Job.")

    job_uuid = uuid.uuid4().hex
    input_path = save_queue_file(job_uuid, ext, content)
    db.create_job(job_uuid, user_id, "tts", file.filename, input_path)

    from src.tasks.tts_tasks import run_tts
    task = run_tts.apply_async(args=[
        job_uuid,
        input_path,
        file.filename,
        voice_id,
        speed,
        stability,
        similarity_boost,
        style,
        use_speaker_boost,
        pause_preset,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("TTS job queued: job_uuid={}, file={}", job_uuid, file.filename)
    return {"job_uuid": job_uuid}
