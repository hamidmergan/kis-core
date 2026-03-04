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
]

_EXCLUDED_VOICES = {
    "adam", "alice", "bella", "charlotte", "clyde", "daniel", "domi", "elli", "ethan",
    "fin", "gigi", "harry", "james", "jeremy", "jessie", "liam", "lily", "michael",
    "mimi", "miss applewood", "nicole", "patrick", "paul", "rover", "roger",
    "sam", "serena", "thomas", "will", "bill", "arnold", "brian", "callum"
}

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


@router.get("/tts/providers")
async def get_tts_providers():
    """Return which TTS providers are currently enabled and reachable (public endpoint)."""
    from src.dependencies import is_elevenlabs_enabled, is_kokoro_enabled, get_kokoro_client
    kokoro_enabled = is_kokoro_enabled()
    if kokoro_enabled:
        client = get_kokoro_client()
        kokoro_enabled = bool(client and client.is_available())
    return {
        "elevenlabs_enabled": is_elevenlabs_enabled(),
        "fish_speech_enabled": False,
        "kokoro_enabled": kokoro_enabled,
    }


@router.post("/kokoro/preview")
async def kokoro_preview(body: dict, _user=Depends(get_current_user)):
    """Synthesize a short preview sample for a Kokoro voice."""
    from fastapi.responses import Response as FastAPIResponse
    from src.dependencies import is_kokoro_enabled, get_kokoro_client
    if not is_kokoro_enabled():
        raise HTTPException(status_code=400, detail="Kokoro nicht aktiv")
    client = get_kokoro_client()
    if not client or not client.is_available():
        raise HTTPException(status_code=503, detail="Kokoro Server nicht erreichbar")
    voice_id = body.get("voice_id", "af_heart")
    audio = client.synthesize_chunk(
        "Hello! This is a preview of the selected voice. I hope you enjoy the sound.",
        voice_id=voice_id,
        speed=1.0,
    )
    return FastAPIResponse(content=audio, media_type="audio/mpeg")


@router.get("/kokoro/voices")
async def list_kokoro_voices():
    """Return all available Kokoro voices from the local server."""
    from src.dependencies import is_kokoro_enabled, get_kokoro_client
    if not is_kokoro_enabled():
        return {"voices": []}
    client = get_kokoro_client()
    if not client or not client.is_available():
        return {"voices": []}
    return {"voices": client.get_voices()}


@router.get("/voices")
async def list_voices():
    """Return all English premade voices from ElevenLabs, sorted A-Z."""
    from src.dependencies import get_settings, is_elevenlabs_enabled
    import httpx

    if not is_elevenlabs_enabled():
        return {"voices": []}

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        return {"voices": _FALLBACK_VOICES}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                params={"show_legacy": "true"},
            )
        if resp.status_code != 200:
            return {"voices": _FALLBACK_VOICES}

        voices = []
        for v in resp.json().get("voices", []):
            if v.get("category") not in ("premade", "professional", "cloned"):
                continue
            voice_name_lower = v["name"].lower().strip()
            if any(voice_name_lower == ex or voice_name_lower.startswith(ex + " ") for ex in _EXCLUDED_VOICES):
                continue
            labels = v.get("labels") or {}
            language = labels.get("language", "").lower().strip()
            accent = labels.get("accent", "").lower().strip()
            if language in _NON_ENGLISH or accent in _NON_ENGLISH:
                continue
            voices.append({
                "voice_id": v["voice_id"],
                "label": v["name"],
                "preview_url": v.get("preview_url"),
            })

        voices.sort(key=lambda x: x["label"].lower())
        return {"voices": voices or _FALLBACK_VOICES}
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
    provider: str = Form("elevenlabs"),  # "elevenlabs" oder "fish_speech"
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

    # Validate provider + client
    if provider == "kokoro":
        from src.dependencies import is_kokoro_enabled, get_kokoro_client
        if not is_kokoro_enabled():
            raise HTTPException(status_code=400, detail="Kokoro TTS ist nicht aktiviert")
        kokoro_client = get_kokoro_client()
        if not kokoro_client or not kokoro_client.is_available():
            raise HTTPException(status_code=503, detail="Kokoro Server nicht erreichbar")
    else:
        from src.dependencies import is_elevenlabs_enabled
        if not is_elevenlabs_enabled():
            raise HTTPException(status_code=400, detail="ElevenLabs ist nicht aktiviert")
        get_elevenlabs_client()

    user_id = current_user.get("user_id", 0)
    if db.has_active_job_for_tool(user_id, ["tts"]):
        raise HTTPException(status_code=409, detail="Du hast bereits einen laufenden TTS-Job.")

    job_uuid = uuid.uuid4().hex
    db.create_job(job_uuid, user_id, "tts", file.filename)
    input_path = save_queue_file(job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

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
        provider,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("TTS job queued: job_uuid={}, file={}", job_uuid, file.filename)
    return {"job_uuid": job_uuid}
