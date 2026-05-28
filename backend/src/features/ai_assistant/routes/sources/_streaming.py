"""File streaming + transcript retrieval."""
import re

from ._shared import (
    Path, Optional, APIRouter, Depends, HTTPException, Request, logger, db,
    get_current_user, get_locale, t,
    FileResponse, Response, StreamingResponse,
    USE_S3, file_exists, get_file, stream_s3_object,
    _require_own_workspace,
)

router = APIRouter(tags=["ki-assistent: sources"])


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/file")
async def stream_source_file(
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

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

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
    disposition = f'inline; filename="{source["filename"]}"'

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


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/regenerate-en-transcript")
async def regenerate_en_transcript(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Dispatch an async Celery task to translate the source-language VTT to English.

    The translation provider is resolved from the ``transcript_translate`` feature route
    configured in the admin KI panel.
    """
    from src.services import feature_router

    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    if workspace.get("transcript_translation_mode", "manual") == "off":
        raise HTTPException(status_code=403, detail=t("ai.transcript.translationDisabled", locale))

    try:
        binding = feature_router.resolve("transcript_translate")
    except feature_router.FeatureNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="transcript_translate not configured — set a translation provider in the admin KI panel",
        )

    base_key = source["file_path"].rsplit(".", 1)[0]
    if not any(file_exists(f"{base_key}_transcript.{lang}.vtt") for lang in ("de",)):
        raise HTTPException(
            status_code=404,
            detail=t("ai.transcript.sourceMissing", locale),
        )

    from src.tasks.aia_tasks import run_translate_transcript_en
    run_translate_transcript_en.delay(source_uuid, binding.provider["id"])
    logger.info(
        "KI Tutor: manual EN translation dispatched for {} (provider_id={})",
        source_uuid, binding.provider["id"],
    )
    return {"uuid": source_uuid, "status": "dispatched", "provider_id": binding.provider["id"]}


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

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    # Only allow lowercase ISO-like language codes (2-5 chars)
    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail=t("ai.transcript.invalidLangCode", locale))

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    if not file_exists(vtt_key):
        raise HTTPException(status_code=404, detail=t("ai.transcript.notAvailable", locale))

    data = get_file(vtt_key)
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

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail=t("ai.transcript.invalidLangCode", locale))

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    return {"exists": file_exists(vtt_key)}
