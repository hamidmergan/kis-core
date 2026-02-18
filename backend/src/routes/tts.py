from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src.dependencies import get_elevenlabs_client, get_settings
from src.services.elevenlabs_client import DEFAULT_VOICE_ID
from src.utils.file_validation import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["tts"])


# ---------- Routes ----------


@router.get("/voices")
async def list_voices():
    """Return available TTS voices."""
    settings = get_settings()
    voices = [
        {"voice_id": DEFAULT_VOICE_ID, "label": "Rachel (Standard)"},
    ]
    if settings.elevenlabs_voice_id:
        voices.append({"voice_id": settings.elevenlabs_voice_id, "label": "Meine Stimme"})
    return {"voices": voices}


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
):
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Nur .docx, .pptx, .md oder .tex erlaubt"
        )

    # Validate pause preset
    valid_presets = {"short", "medium", "long", "very_long"}
    if pause_preset not in valid_presets:
        raise HTTPException(
            status_code=400, detail="Ungültiges Pausen-Preset"
        )

    # Validate file size
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    # Extract text
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")

    try:
        text = extractor(content)
    except Exception as e:
        logger.exception("Text extraction error for file '{}'", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Fehler beim Lesen der Datei: {str(e)}"
        )

    if not text.strip():
        raise HTTPException(status_code=400, detail="Kein Text in der Datei gefunden")

    # Synthesize audio
    client = get_elevenlabs_client()
    try:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("TTS synthesis error for file '{}'", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Fehler bei der Audiogenerierung: {str(e)}"
        )

    logger.info("TTS synthesis completed for file '{}'", file.filename)

    # Build output filename
    stem = Path(file.filename).stem
    output_name = f"{stem}_EN.mp3"
    encoded_name = quote(output_name, safe="")

    return StreamingResponse(
        iter([mp3_bytes]),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_name}\"; filename*=UTF-8''{encoded_name}"
        },
    )
