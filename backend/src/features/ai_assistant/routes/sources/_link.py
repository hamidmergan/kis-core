"""A web page as a source: one link, one PDF, then the ordinary ingest."""
import asyncio
import tempfile
from datetime import datetime, timezone

from pydantic import BaseModel

from src.security.rate_limit import check_upload_limit, record_upload
from src.services.web_page_extract import (
    build_document_html,
    extract_html_page,
    extract_text_page,
    pdf_title_from_url,
    safe_filename,
)
from src.services.web_page_fetch import LinkError, fetch_page, normalize_url, validate_url
from src.services.youtube_link import is_youtube_url
from src.utils.file_validation import validate_or_raise

from . import _upload
from ._shared import (
    Path, APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    _convert_office_to_pdf_path,
    _require_workspace_manage, _workspace_label,
    _require_source_capacity, _register_source_file,
    _unique_filename, _as_http,
)

router = APIRouter(tags=["ki-assistent: sources"])


class LinkBody(BaseModel):
    url: str


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/link")
async def add_link_source(
    workspace_uuid: str,
    body: LinkBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Only check, do not count, so a rejection uses up no slot.
    check_upload_limit(current_user["user_id"], locale=locale)
    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    _require_source_capacity(existing_sources, locale)

    # A YouTube link has its own way in, a PDF of the YouTube page helps nobody.
    if is_youtube_url(body.url):
        raise HTTPException(status_code=400, detail=t("ai.link.useYoutube", locale))

    try:
        url = await asyncio.to_thread(validate_url, body.url)
    except LinkError as e:
        raise _as_http(e, locale)
    wanted = normalize_url(url)
    if any(normalize_url(s["source_url"]) == wanted for s in existing_sources if s.get("source_url")):
        raise HTTPException(status_code=409, detail=t("ai.link.duplicate", locale, label=_workspace_label(locale)))
    existing_names = {(s["filename"] or "").strip().lower() for s in existing_sources}

    # Same brake as the upload, the heavy part is LibreOffice.
    ticket = _upload._claim_upload_slot(_upload._max_concurrent_uploads())
    if ticket is None:
        raise HTTPException(status_code=503, detail=t("ai.source.serverBusy", locale))
    try:
        with tempfile.TemporaryDirectory(prefix="aia_link_") as tmpdir:
            try:
                page = await asyncio.to_thread(fetch_page, url)
                if page.kind == "pdf":
                    validate_or_raise(page.body[:8192], ".pdf", locale)
                    final_path = str(Path(tmpdir) / "page.pdf")
                    Path(final_path).write_bytes(page.body)
                    title = safe_filename(pdf_title_from_url(page.final_url))
                else:
                    extract = extract_html_page if page.kind == "html" else extract_text_page
                    doc = await asyncio.to_thread(extract, page.body, page.final_url)
                    html_path = str(Path(tmpdir) / "page.html")
                    Path(html_path).write_text(
                        build_document_html(doc.title, url, doc.body_html, datetime.now(timezone.utc), locale),
                        encoding="utf-8",
                    )
                    final_path = await asyncio.to_thread(
                        _convert_office_to_pdf_path, html_path, ".html", tmpdir, locale,
                    )
                    title = safe_filename(doc.title)
            except LinkError as e:
                raise _as_http(e, locale)

            filename = _unique_filename(f"{title}.pdf", existing_names)
            result = await _register_source_file(
                workspace, workspace_uuid, final_path, ".pdf", filename,
                current_user["user_id"], locale, source_url=url,
            )
            # Only count now, every rejection above cost nothing.
            record_upload(current_user["user_id"])
            logger.info("KI Tutor: link source {} ({}) added to workspace {}", result["uuid"], url, workspace_uuid)
            return result
    finally:
        _upload._release_upload_slot(ticket)
