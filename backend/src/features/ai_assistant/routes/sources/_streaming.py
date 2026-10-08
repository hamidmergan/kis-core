"""File streaming + transcript retrieval."""
import asyncio
import re

from ._shared import (
    Path, APIRouter, Depends, HTTPException, Request, logger, db, get_current_user,
    get_locale, t, FileResponse,
    Response, StreamingResponse, USE_S3,
    file_exists, get_file, list_keys, stream_s3_object, _require_workspace_manage,
    _load_workspace_source,
    aia_transcript_prefix, aia_vtt_key,
)
from src.features.ai_assistant import schemas
from src.storage import aia_vtt_error_key, delete_file

router = APIRouter(tags=["ki-assistent: sources"])


def _inline_content_disposition(filename: str) -> str:
    """Builds a header for serving that is always latin-1 safe."""
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
    # A YouTube source has no file, the player embeds the video instead.
    if source.get("file_type") == "youtube":
        raise HTTPException(status_code=404, detail=t("ai.youtube.noFile", locale))
    # A page is opened live, it has no file to stream.
    if source.get("file_type") == "page":
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))

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
        # Serve through the backend instead of redirecting so it works on phones too.
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
    body: schemas.TranslateTranscriptBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queues a job that translates the transcript into the chosen language."""
    from src.services import feature_router
    from src.i18n import TRANSCRIPT_LANGUAGES

    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    source = _load_workspace_source(source_uuid, workspace, locale)

    try:
        binding = feature_router.resolve("transcript_translate")
    except feature_router.FeatureNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="transcript_translate not configured — set a translation provider in the admin KI panel",
        )

    # A transcript in the source language must exist, checked with one listing.
    keys = await asyncio.to_thread(list_keys, aia_transcript_prefix(source["file_path"]))
    if not any(k.endswith(".vtt") for k in keys):
        raise HTTPException(status_code=404, detail=t("ai.transcript.sourceMissing", locale))

    target_lang = (body.target_lang or "").strip().lower()
    if target_lang not in TRANSCRIPT_LANGUAGES:
        raise HTTPException(status_code=400, detail=t("ai.workspace.transcriptTargetLangInvalid", locale))
    # Translating a recording into its own language would only delete the original.
    source_lang = (source.get("language") or "").lower()
    if source_lang and source_lang != "unknown" and target_lang == source_lang:
        raise HTTPException(status_code=400, detail=t("ai.transcript.targetEqualsSource", locale))

    # An old note would end the new wait before the task even starts.
    await asyncio.to_thread(delete_file, aia_vtt_error_key(source["file_path"], target_lang))
    from src.tasks import aia_tasks
    aia_tasks.run_translate_transcript.delay(source_uuid, binding.provider["id"], target_lang)
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

    vtt_key = aia_vtt_key(source["file_path"], lang_clean)
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

    vtt_key = aia_vtt_key(source["file_path"], lang_clean)
    if await asyncio.to_thread(file_exists, vtt_key):
        return {"exists": True}
    # A failed run leaves a note, the panel stops waiting on it.
    error_key = aia_vtt_error_key(source["file_path"], lang_clean)
    if await asyncio.to_thread(file_exists, error_key):
        note = await asyncio.to_thread(get_file, error_key)
        return {"exists": False, "error": note.decode("utf-8", "replace")}
    return {"exists": False}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript/langs")
async def get_transcript_langs(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Tells the player the transcript languages that really exist."""
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

    source_lang = (source.get("language") or "").lower() or None

    # One listing instead of a request per language, outside the event loop.
    prefix = aia_transcript_prefix(source["file_path"])
    keys = await asyncio.to_thread(list_keys, prefix)
    vtt_re = re.compile(re.escape(prefix) + r"([a-z]{2,5})\.vtt$")
    found = {m.group(1) for k in keys if (m := vtt_re.search(k))}

    # Source language first, then the targets, only what really exists.
    candidates: list[str] = []
    if source_lang and source_lang != "unknown":
        candidates.append(source_lang)
    candidates.extend(c for c in TRANSCRIPT_LANGUAGES if c not in candidates)
    available = [c for c in candidates if c in found]

    # Without a stored source language the first file found counts as the original.
    if not source_lang or source_lang == "unknown":
        source_lang = available[0] if available else None

    # The translation is whatever else lies there, there is at most one.
    target_lang = next((c for c in available if c != source_lang), None)

    return {"source_lang": source_lang, "target_lang": target_lang, "available": available}
