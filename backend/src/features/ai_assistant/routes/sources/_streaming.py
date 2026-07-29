"""File streaming + transcript retrieval."""
import asyncio
import re

from ._shared import (
    Path, APIRouter, Depends, HTTPException, Request, logger, db, get_current_user,
    get_locale, t, FileResponse,
    Response, StreamingResponse, USE_S3,
    file_exists, get_file, list_keys, stream_s3_object, _require_own_workspace,
    _load_workspace_source,
)

router = APIRouter(tags=["ki-assistent: sources"])


def _inline_content_disposition(filename: str) -> str:
    """Build an `inline` Content-Disposition header that is always latin-1 safe.

    HTTP headers must be latin-1 encodable, but filenames can contain non-Latin-1
    characters (umlauts, or combining marks like the NFD "ü" in "Einführung",
    U+0308). Putting such a name raw into the header crashes StreamingResponse
    with a UnicodeEncodeError. RFC 6266 solves this: an ASCII-only ``filename``
    fallback plus a UTF-8 percent-encoded ``filename*`` that modern browsers
    prefer for display.
    """
    from urllib.parse import quote
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/file")
def stream_source_file(
    workspace_uuid: str,
    source_uuid: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = _load_workspace_source(source_uuid, workspace, locale)

    ext = Path(source["filename"]).suffix.lower()
    media_type_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".webm": "video/webm",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")
    disposition = _inline_content_disposition(source["filename"])

    if USE_S3:
        # Stream through the backend instead of redirecting to a presigned URL:
        # same origin as the app, so it works from smartphones too.
        range_header = request.headers.get("range")
        body_iter, content_length, content_range = stream_s3_object(source["file_path"], range_header)
        headers = {
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        }
        if content_range:
            headers["Content-Range"] = content_range
        return StreamingResponse(
            body_iter,
            status_code=206 if range_header and content_range else 200,
            media_type=media_type,
            headers=headers,
        )

    return FileResponse(
        path=source["file_path"],
        media_type=media_type,
        filename=source["filename"],
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/regenerate-transcript")
async def regenerate_transcript(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Dispatch an async Celery task to translate the source-language VTT into the
    workspace target language (owner-chosen, default English).

    The translation provider is resolved from the ``transcript_translate`` feature route
    configured in the admin KI panel.
    """
    from src.services import feature_router

    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    source = _load_workspace_source(source_uuid, workspace, locale)

    if workspace.get("transcript_translation_mode", "manual") == "off":
        raise HTTPException(status_code=403, detail=t("ai.transcript.translationDisabled", locale))

    try:
        binding = feature_router.resolve("transcript_translate")
    except feature_router.FeatureNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="transcript_translate not configured — set a translation provider in the admin KI panel",
        )

    # A source-language VTT must exist to translate from. One listing instead of a
    # HEAD probe per known language, off the event loop.
    base_key = source["file_path"].rsplit(".", 1)[0]
    keys = await asyncio.to_thread(list_keys, f"{base_key}_transcript.")
    if not any(k.endswith(".vtt") for k in keys):
        raise HTTPException(status_code=404, detail=t("ai.transcript.sourceMissing", locale))

    target_lang = workspace.get("transcript_target_lang") or "en"
    from src.tasks.aia_tasks import run_translate_transcript
    run_translate_transcript.delay(source_uuid, binding.provider["id"], target_lang)
    logger.info(
        "KI Tutor: manual {} translation dispatched for {} (provider_id={})",
        target_lang, source_uuid, binding.provider["id"],
    )
    return {
        "uuid": source_uuid, "status": "dispatched",
        "target_lang": target_lang, "provider_id": binding.provider["id"],
    }


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript")
async def get_transcript_vtt(
    workspace_uuid: str,
    source_uuid: str,
    lang: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return a WebVTT transcript for a media source in the requested language."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = _load_workspace_source(source_uuid, workspace, locale)

    # Only allow lowercase ISO-like language codes (2-5 chars)
    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail=t("ai.transcript.invalidLangCode", locale))

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    if not await asyncio.to_thread(file_exists, vtt_key):
        raise HTTPException(status_code=404, detail=t("ai.transcript.notAvailable", locale))

    data = await asyncio.to_thread(get_file, vtt_key)
    return Response(
        content=data,
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript/exists")
async def get_transcript_exists(
    workspace_uuid: str,
    source_uuid: str,
    lang: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return {exists: bool} for a transcript file. Used for clean polling without 404 spam."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = _load_workspace_source(source_uuid, workspace, locale)

    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail=t("ai.transcript.invalidLangCode", locale))

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    return {"exists": await asyncio.to_thread(file_exists, vtt_key)}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript/langs")
async def get_transcript_langs(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Describe a media source's transcript languages for the player.

    Returns the original (Whisper-detected) language, the workspace target language,
    and the list of codes whose VTT actually exists right now. The player builds its
    track list and language tabs from this instead of hard-coding de/en.
    """
    from src.i18n import TRANSCRIPT_LANGUAGES

    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = _load_workspace_source(source_uuid, workspace, locale)

    base_key = source["file_path"].rsplit(".", 1)[0]
    source_lang = (source.get("language") or "").lower() or None
    target_lang = workspace.get("transcript_target_lang") or "en"

    # One listing instead of a HEAD probe per candidate language: read which
    # "<base>_transcript.<lang>.vtt" files actually exist in a single round trip,
    # off the event loop so the storage call does not block other requests.
    prefix = f"{base_key}_transcript."
    keys = await asyncio.to_thread(list_keys, prefix)
    vtt_re = re.compile(re.escape(prefix) + r"([a-z]{2,5})\.vtt$")
    found = {m.group(1) for k in keys if (m := vtt_re.search(k))}

    # Order: the detected source language first, then every known target. Keep only
    # codes whose VTT exists so the player attaches just the available tracks.
    candidates: list[str] = []
    if source_lang and source_lang != "unknown":
        candidates.append(source_lang)
    candidates.extend(c for c in TRANSCRIPT_LANGUAGES if c not in candidates)
    available = [c for c in candidates if c in found]

    # If the source language was never stored, treat the first available code that
    # is not the target as the original so the UI can still label the tabs.
    if not source_lang or source_lang == "unknown":
        source_lang = next((c for c in available if c != target_lang), available[0] if available else None)

    return {"source_lang": source_lang, "target_lang": target_lang, "available": available}
