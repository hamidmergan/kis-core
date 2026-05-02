import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src.dependencies import get_elevenlabs_client, get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
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
    from src.dependencies import is_elevenlabs_enabled, is_kokoro_enabled, get_kokoro_client, is_mylab_enabled, get_mylab_client
    kokoro_enabled = is_kokoro_enabled()
    if kokoro_enabled:
        client = get_kokoro_client()
        kokoro_enabled = bool(client and client.is_available())
    mylab_enabled = is_mylab_enabled()
    if mylab_enabled:
        client = get_mylab_client()
        mylab_enabled = bool(client and client.is_available())
    return {
        "elevenlabs_enabled": is_elevenlabs_enabled(),
        "fish_speech_enabled": False,
        "kokoro_enabled": kokoro_enabled,
        "mylab_enabled": mylab_enabled,
    }


@router.post("/kokoro/preview")
async def kokoro_preview(
    body: dict,
    _user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Synthesize a short preview sample for a Kokoro voice."""
    from fastapi.responses import Response as FastAPIResponse
    from src.dependencies import is_kokoro_enabled, get_kokoro_client
    if not is_kokoro_enabled():
        raise HTTPException(status_code=400, detail=t("kokoro.notActive", locale))
    client = get_kokoro_client()
    if not client or not client.is_available():
        raise HTTPException(status_code=503, detail=t("kokoro.unreachable", locale))
    voice_id = body.get("voice_id", "af_heart")
    # Use German preview text for German voices
    if voice_id.startswith(("df_", "dm_")):
        preview_text = "Hallo! Dies ist eine Vorschau der ausgewählten Stimme. Ich hoffe, sie gefällt Ihnen."
    else:
        preview_text = "Hello! This is a preview of the selected voice. I hope you enjoy the sound."
    audio = client.synthesize_chunk(
        preview_text,
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


@router.post("/mylab/preview")
async def mylab_preview(
    body: dict,
    _user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Synthesize a short preview sample for a myLab voice."""
    from fastapi.responses import Response as FastAPIResponse
    from src.dependencies import is_mylab_enabled, get_mylab_client
    if not is_mylab_enabled():
        raise HTTPException(status_code=400, detail=t("mylab.notActive", locale))
    client = get_mylab_client()
    if not client or not client.is_available():
        raise HTTPException(status_code=503, detail=t("mylab.ttsUnreachable", locale))
    voice_id = body.get("voice_id", "alloy")
    audio = client.synthesize_chunk(
        "Hallo! Dies ist eine Vorschau der ausgewählten Stimme. Ich hoffe, sie gefällt Ihnen.",
        voice_id=voice_id,
        speed=1.0,
    )
    return FastAPIResponse(content=audio, media_type="audio/mpeg")


@router.get("/mylab/voices")
async def list_mylab_voices():
    """Return all available myLab TTS voices."""
    from src.dependencies import is_mylab_enabled, get_mylab_client
    if not is_mylab_enabled():
        return {"voices": []}
    client = get_mylab_client()
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
    speed: float = Form(1.0),
    stability: float = Form(0.70),
    similarity_boost: float = Form(0.60),
    style: float = Form(0.20),
    use_speaker_boost: bool = Form(True),
    pause_preset: str = Form("medium"),
    provider: str = Form("elevenlabs"),  # "elevenlabs" or "fish_speech"
    voice_label: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue a TTS job: synthesize uploaded document to MP3 via ElevenLabs.

    Returns ``{ job_uuid }`` immediately. Poll ``GET /jobs/{job_uuid}`` for status.
    On success the result contains ``download_url`` for the MP3.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    ext = Path(file.filename).suffix.lower()
    if ext not in TTS_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=t("tts.unsupportedFormat", locale)
        )

    valid_presets = {"short", "medium", "long", "very_long"}
    if pause_preset not in valid_presets:
        raise HTTPException(status_code=400, detail=t("tts.invalidPausePreset", locale))

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb200", locale))

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb200", locale))

    # Validate file type and that text can be extracted (fast check before queuing)
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail=t("tts.unsupportedFileType", locale))

    text = extractor(content)
    if len(text) > TTS_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=t(
                "tts.documentTooLong",
                locale,
                chars=f"{len(text):,}".replace(",", "."),
                maxChars=f"{TTS_MAX_CHARS:,}".replace(",", "."),
            ),
        )

    # Validate provider + client
    if provider == "kokoro":
        from src.dependencies import is_kokoro_enabled, get_kokoro_client
        if not is_kokoro_enabled():
            raise HTTPException(status_code=400, detail=t("kokoro.notEnabled", locale))
        kokoro_client = get_kokoro_client()
        if not kokoro_client or not kokoro_client.is_available():
            raise HTTPException(status_code=503, detail=t("kokoro.unreachable", locale))
    elif provider == "mylab":
        from src.dependencies import is_mylab_enabled, get_mylab_client
        if not is_mylab_enabled():
            raise HTTPException(status_code=400, detail=t("mylab.notEnabled", locale))
        mylab_client = get_mylab_client()
        if not mylab_client or not mylab_client.is_available():
            raise HTTPException(status_code=503, detail=t("mylab.ttsUnreachable", locale))
    else:
        from src.dependencies import is_elevenlabs_enabled
        if not is_elevenlabs_enabled():
            raise HTTPException(status_code=400, detail=t("elevenlabs.notEnabled", locale))
        get_elevenlabs_client()

    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "tts", locale)
    enforce_quota(user_id, "tts", is_admin_user(current_user), locale)

    job_uuid = uuid.uuid4().hex
    db.create_job(job_uuid, user_id, "tts", file.filename, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
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
        voice_label,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("TTS job queued: job_uuid={}, file={}", job_uuid, file.filename)
    return {"job_uuid": job_uuid}
