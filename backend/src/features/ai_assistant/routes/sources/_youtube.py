"""A YouTube video as a source: one link, the pasted transcript, then the ordinary ingest."""
import asyncio
import uuid as _uuid

from pydantic import BaseModel

from src.security.rate_limit import check_upload_limit, record_upload
from src.services.subtitle_converter import segments_to_vtt
from src.services.transcript_paste import parse_transcript
from src.services.web_page_extract import safe_filename
from src.services.web_page_fetch import LinkError
from src.services.youtube_link import fetch_title, parse_youtube_url
from src.storage import save_aia_provided_transcript

from ._shared import (
    APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    _require_workspace_manage, _workspace_label,
    _require_source_capacity, _unique_filename, _enqueue_index_source, _as_http,
)

router = APIRouter(tags=["ki-assistent: sources"])


class YoutubeBody(BaseModel):
    url: str
    transcript: str


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/youtube")
async def add_youtube_source(
    workspace_uuid: str,
    body: YoutubeBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Only check, do not count, so a rejection uses up no slot.
    check_upload_limit(current_user["user_id"], locale=locale)
    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    _require_source_capacity(existing_sources, locale)

    try:
        video = parse_youtube_url(body.url)
        segments = await asyncio.to_thread(parse_transcript, body.transcript)
    except LinkError as e:
        raise _as_http(e, locale)
    if any(s.get("source_url") == video.canonical_url for s in existing_sources):
        raise HTTPException(status_code=409, detail=t("ai.youtube.duplicate", locale, label=_workspace_label(locale)))

    try:
        title = await asyncio.to_thread(fetch_title, video.video_id)
    except LinkError as e:
        raise _as_http(e, locale)

    existing_names = {(s["filename"] or "").strip().lower() for s in existing_sources}
    filename = _unique_filename(f"{safe_filename(title)}.youtube", existing_names)
    source_uuid = _uuid.uuid4().hex

    def _save_provided_transcript() -> str:
        """Build the VTT and write it, both off the event loop."""
        return save_aia_provided_transcript(workspace["user_id"], workspace_uuid, source_uuid, segments_to_vtt(segments))

    # The transcript hangs off the owner, not off the person adding it.
    file_path = await asyncio.to_thread(_save_provided_transcript)
    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=source_uuid,
        filename=filename,
        file_path=file_path,
        file_type="youtube",
        source_url=video.canonical_url,
    )
    _enqueue_index_source(source_uuid, current_user["user_id"], locale)
    # Only count now, every rejection above cost nothing.
    record_upload(current_user["user_id"])
    logger.info("KI Tutor: youtube source {} ({}) added to workspace {}", source_uuid, video.video_id, workspace_uuid)
    return {"uuid": source_uuid, "filename": filename, "status": "pending", "source_url": video.canonical_url}
