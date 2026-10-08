"""A page from Pages as a source: read as text for the chat, opened live for every member."""
import asyncio
import json
import uuid as _uuid

from fastapi import Query, Response
from pydantic import BaseModel

from src.features.ai_assistant.routes._workspace_access import _require_workspace_access
from src.security.rate_limit import check_upload_limit, record_upload
from src.services.web_page_extract import safe_filename
from src.storage import aia_source_base, aia_source_key, get_file, get_job_file, put_bytes

from ._shared import (
    APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    _require_workspace_manage, _workspace_label, _load_workspace_source,
    _require_source_capacity, _unique_filename, _enqueue_index_source,
)

router = APIRouter(tags=["ki-assistent: sources"])

# A page source keeps its page as a link in this form, so a second add of the same page is caught.
LINK_PREFIX = "pages:"
_IMAGE_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


def page_link(job_uuid: str) -> str:
    return f"{LINK_PREFIX}{job_uuid}"


def sidecar_key(file_path: str) -> str:
    """Where a page source notes which page it stands for and the anchors of its sections."""
    return f"{aia_source_base(file_path)}_page.json"


def read_sidecar(file_path: str) -> dict:
    try:
        return json.loads(get_file(sidecar_key(file_path)))
    except Exception:  # noqa: BLE001 - a missing note means the page is gone
        return {}


def write_sidecar(file_path: str, data: dict) -> None:
    put_bytes(sidecar_key(file_path), json.dumps(data).encode())


class PageBody(BaseModel):
    job_uuid: str


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/page")
async def add_page_source(
    workspace_uuid: str,
    body: PageBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Puts one of the person's own finished pages into the workspace."""
    from src.features.pages import schema
    from src.tasks.pages_tasks import load_page

    user_id = current_user["user_id"]
    workspace = _require_workspace_manage(workspace_uuid, user_id, locale=locale)
    job = db.get_job(body.job_uuid)
    if not job or job["tool"] != "pages" or job["user_id"] != user_id or job["status"] != "success":
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    check_upload_limit(user_id, locale=locale)
    existing = db.get_aia_sources_by_workspace(workspace["id"])
    _require_source_capacity(existing, locale)
    if any(s.get("source_url") == page_link(body.job_uuid) for s in existing):
        raise HTTPException(status_code=409, detail=t("ai.page.duplicate", locale, label=_workspace_label(locale)))

    page, _ = await asyncio.to_thread(load_page, user_id, body.job_uuid)
    if not page:
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    names = {(s["filename"] or "").strip().lower() for s in existing}
    filename = _unique_filename(f"{safe_filename(schema.title_of(page) or 'Page')}.page", names)
    source_uuid = _uuid.uuid4().hex
    # No file of its own: the key only anchors the note and the text the ingest writes beside it.
    file_path = aia_source_key(workspace["user_id"], workspace_uuid, source_uuid, ".page")
    await asyncio.to_thread(write_sidecar, file_path, {"job_uuid": body.job_uuid, "owner_user_id": user_id})
    db.create_aia_source(workspace_id=workspace["id"], uuid=source_uuid, filename=filename,
                         file_path=file_path, file_type="page", source_url=page_link(body.job_uuid))
    _enqueue_index_source(source_uuid, user_id, locale)
    record_upload(user_id)
    logger.info("KI Tutor: page source {} (page {}) added to workspace {}", source_uuid,
                body.job_uuid[:8], workspace_uuid)
    return {"uuid": source_uuid, "filename": filename, "status": "pending",
            "source_url": page_link(body.job_uuid)}


def _viewer_page(workspace_uuid: str, source_uuid: str, user_id: int, locale: str) -> tuple[dict, dict, dict]:
    """The page behind a source, hidden sections still in, every caller leaves them out."""
    from src.tasks.pages_tasks import load_page

    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    source = _load_workspace_source(source_uuid, workspace, locale)
    note = read_sidecar(source["file_path"]) if source.get("file_type") == "page" else {}
    job = db.get_job(note["job_uuid"]) if note.get("job_uuid") else None
    page = load_page(job["user_id"], job["job_uuid"])[0] if job and job["tool"] == "pages" else None
    if not page:
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    return workspace, {**note, "owner_user_id": job["user_id"]}, page


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/page")
def get_page_source(
    workspace_uuid: str,
    source_uuid: str,
    sprache: str = Query(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The live page for the workspace's members, with the anchors its citations jump to."""
    from src.features.pages import schema
    from src.tasks import pages_tasks as pt

    workspace, note, page = _viewer_page(workspace_uuid, source_uuid, current_user["user_id"], locale)
    gezeigt = pt.in_language(note["owner_user_id"], note["job_uuid"], page, sprache)
    return {"page": schema.for_viewers(gezeigt), "limits": schema.limits(), "anchors": note.get("anchors") or [],
            "languages": pt.readable(note["owner_user_id"], note["job_uuid"], page),
            "language": pt.key_of(gezeigt),
            "workspace": {"uuid": workspace_uuid, "title": workspace.get("title") or ""}}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/page/images/{name}")
def get_page_source_image(
    workspace_uuid: str,
    source_uuid: str,
    name: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    from src.tasks import pages_tasks as pt

    _, note, page = _viewer_page(workspace_uuid, source_uuid, current_user["user_id"], locale)
    if name not in pt.viewer_images(note["owner_user_id"], note["job_uuid"], page):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    try:
        data = get_job_file(note["owner_user_id"], note["job_uuid"], name)
    except Exception:  # noqa: BLE001 - a missing picture is a 404
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale)) from None
    return Response(content=data, media_type=_IMAGE_TYPES[name[name.rfind("."):]],
                    headers={"Cache-Control": "private, max-age=86400"})
