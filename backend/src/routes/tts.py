import asyncio
import json
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
from src.services.open_jobs import create_counted_job, enforce_open_jobs
from src.services import tts_job_provider
from src.services.tts_job_provider import pick
from src import database as db
from src.storage import save_job_file, save_queue_file_from_path
from src.utils.file_validation import (
    TTS_EXTENSIONS,
    TTS_MAX_CHARS,
    sanitize_pasted_text,
    validate_or_raise,
)
from src.services.tool_limits import max_upload_bytes
from src.utils.text_extraction import EXTRACTORS
from src.dependencies_rbac import require_tool_access
from src.routes._shared import enforce_upload_size, input_name, stage_input
from src.routes.uploads import tool_access
from src.services import direct_upload

direct_upload.register("tts", direct_upload.UploadRule(
    TTS_EXTENSIONS, lambda: max_upload_bytes(), tool_access("tts")))

router = APIRouter(
    tags=["tts"],
    dependencies=[Depends(require_tool_access("tts"))],
)


# ─── Provider + Voice catalogue ────────────────────────────────────────────


@router.get("/tts/providers-with-voices")
async def get_tts_providers_with_voices(
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Reachable speech providers with their voices, the starred one first, plus the voice to preselect."""
    from src.dependencies import get_reachable_tts_providers_with_voices
    from src.i18n import TRANSCRIPT_LANGUAGES
    from src.services import tts_standard
    from src.services.own_tts import display_name
    providers = await get_reachable_tts_providers_with_voices(current_user)
    # Same cap as every other language picker: German, English, or language-less.
    allowed_langs = {"", *TRANSCRIPT_LANGUAGES}
    star = tts_standard.star_id()
    # Strip sensitive fields before sending to frontend
    listed = [
        {
            "id": p["id"],
            "name": display_name(p, locale),
            # A person's own interface, it never becomes the preselected voice.
            "own": p.get("owner_user_id") is not None,
            "voices": [
                v for v in p.get("voices", [])
                if (v.get("language") or "").lower() in allowed_langs
            ],
        }
        for p in tts_standard.star_first(providers, star)
    ]
    default = tts_standard.standard_voice([p for p in listed if not p["own"]], star,
                                          tts_standard.default_voice_setting())
    return {
        "providers": listed,
        "default": {"provider_id": default[0], "voice_id": default[1]} if default else None,
    }


@router.post("/tts/providers/{provider_id}/preview")
def tts_provider_preview(
    provider_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Synthesize a short preview sample for a voice on the given provider."""
    from fastapi.responses import Response as FastAPIResponse
    from src.services.own_tts.access import check_voice_provider
    from src.services.tts_voice_preview import preview_audio

    check_voice_provider(provider_id, current_user, locale)
    audio = preview_audio(provider_id, body.get("voice_id", ""), locale, current_user.get("user_id"))
    return FastAPIResponse(content=audio, media_type="audio/mpeg")


# ─── TTS Job ───────────────────────────────────────────────────────────────


def _too_long(key: str, chars: int, locale: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=t(
            key,
            locale,
            chars=f"{chars:,}".replace(",", "."),
            maxChars=f"{TTS_MAX_CHARS:,}".replace(",", "."),
        ),
    )


def _stage_text(text: str, tmpdir: str, locale: str) -> str:
    """Writes the pasted text into a file and returns its path."""
    cleaned = sanitize_pasted_text(text)
    if not cleaned:
        raise HTTPException(status_code=400, detail=t("tts.textEmpty", locale))
    if len(cleaned) > TTS_MAX_CHARS:
        raise _too_long("tts.textTooLong", len(cleaned), locale)
    tmp_path = os.path.join(tmpdir, "input.txt")
    with open(tmp_path, "wb") as out:
        out.write(cleaned.encode("utf-8"))
    return tmp_path


async def _stage_file(filename: str, file: UploadFile | None, upload_token: str | None, user_id: int,
                      request: Request, tmpdir: str, locale: str) -> tuple[str, str]:
    """Puts the upload on disk and checks it, returns its ending and its path."""
    ext = Path(filename).suffix.lower()
    if ext not in TTS_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("tts.unsupportedFormat", locale))

    enforce_upload_size(request, locale)

    tmp_path = os.path.join(tmpdir, f"input{ext}")
    total, head = await stage_input(file, upload_token, "tts", user_id, tmp_path, max_upload_bytes(), locale)
    if not total:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    validate_or_raise(head, ext, locale)

    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail=t("tts.unsupportedFileType", locale))

    extracted = await asyncio.to_thread(extractor, tmp_path)
    if len(extracted) > TTS_MAX_CHARS:
        raise _too_long("tts.documentTooLong", len(extracted), locale)
    return ext, tmp_path


async def _check_provider(provider_id: int, voice_id: str, current_user: dict, locale: str) -> None:
    """Refuses a provider that is unknown or down, unless the admin's fallback may take the job."""
    from src.dependencies import get_tts_client_for_provider
    from src.services.own_tts.access import check_voice_provider
    check_voice_provider(provider_id, current_user, locale)
    try:
        client = get_tts_client_for_provider(provider_id, current_user.get("user_id"))
    except RuntimeError:
        raise HTTPException(status_code=400, detail=t("tts.providerNotFound", locale))
    # The chosen one seen exactly as pick sees it, an own probe could disagree and refuse for nothing.
    if client is None or not await asyncio.to_thread(tts_job_provider.is_there, provider_id):
        # The admin's fallback may take over the whole job, the job itself decides at its start.
        if not (await asyncio.to_thread(pick, provider_id, [voice_id])).fallback:
            if client is None:
                raise HTTPException(status_code=400, detail=t("tts.providerNotFound", locale))
            raise HTTPException(status_code=503, detail=t("tts.providerUnavailable", locale))


@router.post("/tts")
async def text_to_speech(
    request: Request,
    file: UploadFile | None = File(None),
    upload_token: str | None = Form(None),
    text: str = Form(""),
    voice_id: str = Form(""),
    speed: float = Form(1.0),
    provider_id: int = Form(...),
    voice_label: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue a TTS job: synthesize uploaded document or pasted text to MP3."""
    # A large file arrives as the token of a direct upload, a small one as the file itself.
    incoming = await asyncio.to_thread(input_name, file, upload_token, "tts", current_user.get("user_id", 0), locale)
    has_file = bool(incoming)
    has_text = bool(text and text.strip())
    if has_file and has_text:
        raise HTTPException(status_code=400, detail=t("tts.bothInputs", locale))
    if not has_file and not has_text:
        raise HTTPException(status_code=400, detail=t("tts.noInput", locale))

    # Both inputs end up as a file, the upload never sits in memory.
    with tempfile.TemporaryDirectory(prefix="tts_upload_") as tmpdir:
        if has_text:
            ext, source_filename = ".txt", "text.txt"
            tmp_path = _stage_text(text, tmpdir, locale)
        else:
            source_filename = incoming
            ext, tmp_path = await _stage_file(incoming, file, upload_token, current_user.get("user_id", 0),
                                              request, tmpdir, locale)

        await _check_provider(provider_id, voice_id, current_user, locale)

        user_id = current_user.get("user_id", 0)
        enforce_open_jobs(user_id, locale, "tts")
        enforce_tool_burst(user_id, "tts", locale)
        enforce_quota(user_id, "tts", is_admin_user(current_user), locale)

        job_uuid = uuid.uuid4().hex
        create_counted_job(job_uuid, user_id, "tts", source_filename, locale=locale)
        input_path = await asyncio.to_thread(save_queue_file_from_path, user_id, job_uuid, ext, tmp_path)
        db.set_job_input_path(job_uuid, input_path)
        # Laid down now and not at the start, so a job that never ran can still be resumed.
        save_job_file(user_id, job_uuid, "tts_params.json", json.dumps({
            "voice_id": voice_id, "voice_label": voice_label, "speed": speed, "provider_id": provider_id,
        }).encode())

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
