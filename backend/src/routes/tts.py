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
from src.utils.file_validation import TTS_EXTENSIONS, MAX_UPLOAD_BYTES, TTS_MAX_CHARS, validate_or_raise
from src.utils.text_extraction import EXTRACTORS
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["tts"],
    dependencies=[Depends(require_tool_access("tts"))],
)


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
    # Kokoro is restricted to English voices: preview text is always English
    # to match the voice character, regardless of the user's UI locale.
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
    # Voice id encodes language (e.g. "alloy@de"); preview text follows that
    # so users hear the voice in the language they actually selected. Fall
    # back to UI locale for legacy voice ids without a suffix.
    from src.services.openai_compat_tts import _split_voice_language
    _, voice_lang = _split_voice_language(voice_id)
    effective_lang = voice_lang or locale
    preview_text = (
        "Hello! This is a preview of the selected voice. I hope you enjoy the sound."
        if effective_lang == "en"
        else "Hallo! Dies ist eine Vorschau der ausgewählten Stimme. Ich hoffe, sie gefällt Ihnen."
    )
    audio = client.synthesize_chunk(
        preview_text,
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


def _sanitize_tts_text(raw: str) -> str:
    """Normalize free-form text for safe pipeline use.

    Strips NULs and other C0 control bytes (except common whitespace), normalises
    newlines to ``\n``, and trims surrounding whitespace. The DB layer uses
    parameterised statements throughout, so the goal here is not SQL escaping
    but defence-in-depth: keep the stored text printable and free of bytes
    that could break extractors, log lines, or downstream HTTP bodies.
    """
    # Normalise line endings before stripping control chars so \r\n -> \n
    cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Keep tab / newline, drop the rest of C0 plus DEL
    cleaned = "".join(
        ch for ch in cleaned
        if ch in ("\t", "\n") or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned.strip()


@router.post("/tts")
async def text_to_speech(
    request: Request,
    file: UploadFile | None = File(None),
    text: str = Form(""),
    voice_id: str = Form(""),
    speed: float = Form(1.0),
    stability: float = Form(0.70),
    similarity_boost: float = Form(0.60),
    style: float = Form(0.20),
    use_speaker_boost: bool = Form(True),
    pause_preset: str = Form("medium"),
    provider: str = Form("elevenlabs"),
    voice_label: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue a TTS job: synthesize uploaded document or pasted text to MP3.

    Either ``file`` or ``text`` must be supplied. Returns ``{ job_uuid }``
    immediately. Poll ``GET /jobs/{job_uuid}`` for status. On success the
    result contains ``download_url`` for the MP3.
    """
    valid_presets = {"short", "medium", "long", "very_long"}
    if pause_preset not in valid_presets:
        raise HTTPException(status_code=400, detail=t("tts.invalidPausePreset", locale))

    has_file = bool(file and file.filename)
    has_text = bool(text and text.strip())
    if has_file and has_text:
        raise HTTPException(status_code=400, detail=t("tts.bothInputs", locale))
    if not has_file and not has_text:
        raise HTTPException(status_code=400, detail=t("tts.noInput", locale))

    if has_text:
        cleaned = _sanitize_tts_text(text)
        if not cleaned:
            raise HTTPException(status_code=400, detail=t("tts.textEmpty", locale))
        if len(cleaned) > TTS_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=t(
                    "tts.textTooLong",
                    locale,
                    chars=f"{len(cleaned):,}".replace(",", "."),
                    maxChars=f"{TTS_MAX_CHARS:,}".replace(",", "."),
                ),
            )
        ext = ".txt"
        content = cleaned.encode("utf-8")
        # Synthetic filename so the result MP3 still gets a sensible stem.
        source_filename = "text.txt"
    else:
        assert file is not None  # narrowed by has_file
        ext = Path(file.filename).suffix.lower()
        if ext not in TTS_EXTENSIONS:
            raise HTTPException(
                status_code=400, detail=t("tts.unsupportedFormat", locale)
            )

        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=t("file.tooLargeMb200", locale))

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=t("file.tooLargeMb200", locale))
        validate_or_raise(content, ext, locale)

        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise HTTPException(status_code=400, detail=t("tts.unsupportedFileType", locale))

        extracted = extractor(content)
        if len(extracted) > TTS_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=t(
                    "tts.documentTooLong",
                    locale,
                    chars=f"{len(extracted):,}".replace(",", "."),
                    maxChars=f"{TTS_MAX_CHARS:,}".replace(",", "."),
                ),
            )
        source_filename = file.filename

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
    db.create_job(job_uuid, user_id, "tts", source_filename, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.tts_tasks import run_tts
    task = run_tts.apply_async(args=[
        job_uuid,
        input_path,
        source_filename,
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

    logger.info("TTS job queued: job_uuid={}, source={}", job_uuid, source_filename)
    return {"job_uuid": job_uuid}
