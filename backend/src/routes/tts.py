import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src import database as db
from src.storage import save_queue_file_from_path
from src.utils.file_validation import (
    TTS_EXTENSIONS,
    TTS_MAX_CHARS,
    sanitize_pasted_text,
    validate_or_raise,
)
from src.services.tool_limits import max_upload_bytes
from src.utils.text_extraction import EXTRACTORS
from src.utils.upload_stream import stream_upload_to_path
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["tts"],
    dependencies=[Depends(require_tool_access("tts"))],
)


# ─── Provider + Voice catalogue ────────────────────────────────────────────


@router.get("/tts/providers-with-voices")
async def get_tts_providers_with_voices():
    """Reachable speech providers with their voices, unreachable ones stay hidden."""
    from src.dependencies import get_reachable_tts_providers_with_voices
    providers = await get_reachable_tts_providers_with_voices()
    # Strip sensitive fields before sending to frontend
    return {
        "providers": [
            {
                "id": p["id"],
                "name": p["name"],
                "voices": p.get("voices", []),
            }
            for p in providers
        ]
    }


@router.post("/tts/providers/{provider_id}/preview")
def tts_provider_preview(
    provider_id: int,
    body: dict,
    _user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Synthesize a short preview sample for a voice on the given provider."""
    from fastapi.responses import Response as FastAPIResponse
    from src.services.tts_voice_preview import preview_audio

    audio = preview_audio(provider_id, body.get("voice_id", ""), locale)
    return FastAPIResponse(content=audio, media_type="audio/mpeg")


# ─── TTS Job ───────────────────────────────────────────────────────────────


@router.post("/tts")
async def text_to_speech(
    request: Request,
    file: UploadFile | None = File(None),
    text: str = Form(""),
    voice_id: str = Form(""),
    speed: float = Form(1.0),
    provider_id: int = Form(...),
    voice_label: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue a TTS job: synthesize uploaded document or pasted text to MP3."""
    has_file = bool(file and file.filename)
    has_text = bool(text and text.strip())
    if has_file and has_text:
        raise HTTPException(status_code=400, detail=t("tts.bothInputs", locale))
    if not has_file and not has_text:
        raise HTTPException(status_code=400, detail=t("tts.noInput", locale))

    # Both inputs end up as a file, the upload never sits in memory.
    with tempfile.TemporaryDirectory(prefix="tts_upload_") as tmpdir:
        if has_text:
            cleaned = sanitize_pasted_text(text)
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
            source_filename = "text.txt"
            tmp_path = os.path.join(tmpdir, "input.txt")
            with open(tmp_path, "wb") as out:
                out.write(cleaned.encode("utf-8"))
        else:
            assert file is not None
            ext = Path(file.filename).suffix.lower()
            if ext not in TTS_EXTENSIONS:
                raise HTTPException(status_code=400, detail=t("tts.unsupportedFormat", locale))

            content_length = request.headers.get("content-length")
            if content_length is not None and int(content_length) > max_upload_bytes():
                raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

            tmp_path = os.path.join(tmpdir, f"input{ext}")
            total, head = await stream_upload_to_path(file, tmp_path, max_upload_bytes(), locale)
            if not total:
                raise HTTPException(status_code=400, detail=t("file.empty", locale))
            validate_or_raise(head, ext, locale)

            extractor = EXTRACTORS.get(ext)
            if extractor is None:
                raise HTTPException(status_code=400, detail=t("tts.unsupportedFileType", locale))

            extracted = extractor(tmp_path)
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

        # Validate provider
        from src.dependencies import get_tts_client_for_provider
        try:
            client = get_tts_client_for_provider(provider_id)
        except RuntimeError:
            raise HTTPException(status_code=400, detail=t("tts.providerNotFound", locale))
        if client is None:
            raise HTTPException(status_code=400, detail=t("tts.providerNotFound", locale))
        if not client.is_available():
            raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))

        user_id = current_user.get("user_id", 0)
        enforce_tool_burst(user_id, "tts", locale)
        enforce_quota(user_id, "tts", is_admin_user(current_user), locale)

        job_uuid = uuid.uuid4().hex
        db.create_job(job_uuid, user_id, "tts", source_filename, locale=locale)
        input_path = save_queue_file_from_path(user_id, job_uuid, ext, tmp_path)
        db.set_job_input_path(job_uuid, input_path)

    from src.tasks.tts_tasks import run_tts
    task = run_tts.apply_async(args=[
        job_uuid,
        input_path,
        source_filename,
        voice_id,
        speed,
        provider_id,
        voice_label,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("TTS job queued: job_uuid={}, provider_id={}, source={}", job_uuid, provider_id, source_filename)
    return {"job_uuid": job_uuid}
