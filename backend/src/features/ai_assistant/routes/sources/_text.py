"""Pasted text as a source: short enough to be its own summary, rendered as a PDF for the viewer."""
import asyncio
import html as _html
import re
import tempfile
import uuid as _uuid

from pydantic import BaseModel

from src.limits import AIA_TEXT_SOURCE_MAX_CHARS
from src.security.rate_limit import check_upload_limit, record_upload
from src.services.web_page_extract import safe_filename
from src.storage import aia_text_key, get_file, put_bytes, put_file

from . import _upload
from ._shared import (
    Path, APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    _convert_office_to_pdf_path, _save_source_file_path,
    _require_workspace_manage, _load_workspace_source,
    _require_source_capacity, _unique_filename, _enqueue_index_source,
)
from src.features.ai_assistant.tasks.ingestion import _zahl

router = APIRouter(tags=["ki-assistent: sources"])

FILE_TYPE = "text"


class NewTextBody(BaseModel):
    title: str
    text: str


class EditTextBody(BaseModel):
    text: str


def _clean_text(raw: str, locale: str) -> str:
    """Line ends unified and the length checked, the text itself is never cut."""
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise HTTPException(status_code=400, detail=t("ai.text.empty", locale))
    if len(text) > AIA_TEXT_SOURCE_MAX_CHARS:
        raise HTTPException(status_code=400, detail=t(
            "ai.text.tooLong", locale,
            chars=_zahl(len(text), locale), max=_zahl(AIA_TEXT_SOURCE_MAX_CHARS, locale),
        ))
    return text


def _document_html(title: str, text: str) -> str:
    """Title and paragraphs as plain HTML, single line breaks kept."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "".join(f"<p>{_html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{_html.escape(title)}</title></head><body>"
        f"<h1>{_html.escape(title)}</h1>{body}</body></html>"
    )


async def _render_pdf(title: str, text: str, tmpdir: str, locale: str) -> str:
    """LibreOffice behind the same brake as every upload."""
    ticket = await _upload._wait_for_upload_slot(_upload._max_concurrent_uploads())
    if ticket is None:
        raise HTTPException(status_code=503, detail=t("ai.source.serverBusy", locale))
    try:
        html_path = Path(tmpdir) / "text.html"
        html_path.write_text(_document_html(title, text), encoding="utf-8")
        return await asyncio.to_thread(_convert_office_to_pdf_path, str(html_path), ".html", tmpdir, locale)
    finally:
        _upload._release_upload_slot(ticket)


def _load_text_source(workspace_uuid: str, source_uuid: str, user_id: int, locale: str) -> dict:
    workspace = _require_workspace_manage(workspace_uuid, user_id, locale=locale)
    source = _load_workspace_source(source_uuid, workspace, locale)
    if source.get("file_type") != FILE_TYPE:
        raise HTTPException(status_code=400, detail=t("ai.text.notText", locale))
    return source


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/text")
async def add_text_source(
    workspace_uuid: str,
    body: NewTextBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Only check, do not count, so a rejection uses up no slot.
    check_upload_limit(current_user["user_id"], locale=locale)
    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    _require_source_capacity(existing_sources, locale)

    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail=t("ai.text.noTitle", locale))
    text = _clean_text(body.text, locale)
    existing_names = {(s["filename"] or "").strip().lower() for s in existing_sources}
    filename = _unique_filename(f"{safe_filename(title)}.pdf", existing_names)
    source_uuid = _uuid.uuid4().hex

    with tempfile.TemporaryDirectory(prefix="aia_text_") as tmpdir:
        pdf_path = await _render_pdf(title, text, tmpdir, locale)
        # The file hangs off the owner, not off the person adding it.
        file_path = await asyncio.to_thread(
            _save_source_file_path, workspace["user_id"], workspace_uuid, source_uuid, ".pdf", pdf_path,
        )
    # Written before the ingest starts, it reads the summary from here.
    await asyncio.to_thread(put_bytes, aia_text_key(file_path), text.encode("utf-8"))
    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=source_uuid,
        filename=filename,
        file_path=file_path,
        file_type=FILE_TYPE,
    )
    _enqueue_index_source(source_uuid, current_user["user_id"], locale)
    # Only count now, every rejection above cost nothing.
    record_upload(current_user["user_id"])
    logger.info("KI Tutor: text source {} ({} chars) added to workspace {}", source_uuid, len(text), workspace_uuid)
    return {"uuid": source_uuid, "filename": filename, "status": "pending", "source_url": None,
            "file_type": FILE_TYPE}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/text")
def get_text_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The pasted text for editing, managers only."""
    source = _load_text_source(workspace_uuid, source_uuid, current_user["user_id"], locale)
    return {"text": get_file(aia_text_key(source["file_path"])).decode("utf-8")}


@router.put("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/text")
async def edit_text_source(
    workspace_uuid: str,
    source_uuid: str,
    body: EditTextBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Replaces the text and reads the source in again."""
    source = _load_text_source(workspace_uuid, source_uuid, current_user["user_id"], locale)
    if source["status"] in ("pending", "indexing") or source.get("progress"):
        raise HTTPException(status_code=409, detail=t("ai.text.busy", locale))
    text = _clean_text(body.text, locale)
    title = Path(source["filename"]).stem

    with tempfile.TemporaryDirectory(prefix="aia_text_") as tmpdir:
        pdf_path = await _render_pdf(title, text, tmpdir, locale)
        await asyncio.to_thread(put_file, source["file_path"], pdf_path)
    await asyncio.to_thread(put_bytes, aia_text_key(source["file_path"]), text.encode("utf-8"))

    db.delete_aia_chunks_by_source(source["id"])
    db.reset_aia_source_for_retry(source_uuid)
    _enqueue_index_source(source_uuid, current_user["user_id"], locale)
    logger.info("KI Tutor: text source {} edited ({} chars)", source_uuid, len(text))
    return {"uuid": source_uuid, "status": "pending"}
