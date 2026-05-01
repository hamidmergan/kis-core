"""File streaming + transcript retrieval."""
import re

from ._shared import (
    Path, Optional, APIRouter, Depends, HTTPException, Request, logger, db,
    get_current_user,
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
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

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
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Dispatch an async Celery task to translate the source-language VTT to English.

    If ``provider`` is omitted, falls back to the admin-configured default
    (``transcript_translation_provider`` setting; defaults to ``llm``).
    """
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"])
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    if workspace.get("transcript_translation_mode", "manual") == "off":
        raise HTTPException(status_code=403, detail="EN-Übersetzung ist für diesen Workspace deaktiviert")

    effective_provider = provider or db.get_setting("transcript_translation_provider", "llm")
    if effective_provider not in ("deepl", "llm"):
        raise HTTPException(status_code=400, detail="Ungültiger Provider")

    base_key = source["file_path"].rsplit(".", 1)[0]
    if not any(file_exists(f"{base_key}_transcript.{lang}.vtt") for lang in ("de",)):
        raise HTTPException(
            status_code=404,
            detail="Kein Quell-Transkript gefunden. Neu-Übersetzung nicht möglich.",
        )

    from src.tasks.aia_tasks import run_translate_transcript_en
    run_translate_transcript_en.delay(source_uuid, effective_provider)
    logger.info(
        "KI Tutor: manual EN translation dispatched for {} (provider={})",
        source_uuid, effective_provider,
    )
    return {"uuid": source_uuid, "status": "dispatched", "provider": effective_provider}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/transcript")
async def get_transcript_vtt(
    workspace_uuid: str,
    source_uuid: str,
    lang: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a WebVTT transcript for a media source in the requested language."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    # Only allow lowercase ISO-like language codes (2-5 chars)
    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail="Ungültiger Sprachcode")

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    if not file_exists(vtt_key):
        raise HTTPException(status_code=404, detail="Transkript nicht verfügbar")

    data = get_file(vtt_key)
    return Response(
        content=data,
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )
