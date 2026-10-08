"""Pages routes: create, list, edit and share a page, and the read-only view behind a link.

The owner routes need the pages tool, the shared routes only a login, so a student without
the tool still reads what a teacher shared.
"""

import asyncio
import json
from datetime import datetime, timezone
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.dependencies_rbac import require_tool_access
from src.features.pages import repository as repo
from src.features.pages import schema
from src.features.summary.models import INSTRUCTIONS_FILE
from src.i18n import get_locale, t
from src.limits import PAGES_MAX_JSON_BYTES, PAGES_MAX_PER_USER, SUMMARY_MAX_SOURCES
from src.quotas import enforce_quota
from src.routes.material_measure import measure_router
from src.security.rate_limit import enforce_tool_burst
from src.services import feature_provider_choices, sources
from src.services.job_statistik import angaben_lesen
from src.services.open_jobs import create_counted_job, enforce_open_jobs
from src.services.tool_limits import max_upload_bytes
from src.storage import get_job_file, save_job_file
from src.tasks.pages_tasks import PARAMS_FILE, USER_PAGE_FILE, load_page
from src.utils.file_validation import SUMMARY_EXTENSIONS

router = APIRouter(tags=["pages"], dependencies=[Depends(require_tool_access("pages"))])
router.include_router(measure_router("pages", "summary"))
shared_router = APIRouter(tags=["pages"])

_UUID = re.compile(r"^[0-9a-f]{32}$")
_CODE = re.compile(r"^[A-Za-z0-9]{6,32}$")
_IMAGE_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


def _own_job(job_uuid: str, user: dict, locale: str) -> dict:
    """The page job of this person, 404 for anything else so foreign pages stay invisible."""
    job = db.get_job(job_uuid) if _UUID.match(job_uuid) else None
    if not job or job["tool"] != "pages" or job["user_id"] != user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    return job


def _progress(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


def _dt(v) -> str | None:
    return (v.isoformat() + "Z") if hasattr(v, "isoformat") else v


def _card(user_id: int, row: dict) -> dict:
    """One page as its card shows it: title, picture, sources, share state."""
    page, _ = load_page(user_id, row["job_uuid"]) if row["status"] == "success" else (None, False)
    return {
        "job_uuid": row["job_uuid"],
        "status": row["status"],
        "progress": _progress(row["progress"]),
        "error": row["error_message"],
        "title": (schema.title_of(page) if page else "") or "",
        "image": schema.first_image(page) if page else "",
        "sources": row["original_filename"],
        "created_at": _dt(row["created_at"]),
        "updated_at": (page or {}).get("saved_at") or _dt(row["completed_at"] or row["created_at"]),
        # What the page was made from and with, shown to the owner behind the info icon.
        "info": angaben_lesen({"user_id": user_id, "job_uuid": row["job_uuid"], "tool": "pages"})
        if row["status"] == "success" else {},
        "shared": bool(row["shared"]),
        "code": row["code"] if row["shared"] else None,
    }


@router.get("/pages/providers")
async def list_page_providers(_user: dict = Depends(get_current_user)):
    """Reachable chat providers, the page is written by the chat model."""
    return await feature_provider_choices.list_reachable_choices("chat")


@router.get("/pages")
def list_pages(current_user: dict = Depends(get_current_user)):
    """Every page of the person, newest first, and the collection link with its count."""
    user_id = current_user.get("user_id", 0)
    rows = repo.list_pages(user_id)
    return {
        "pages": [_card(user_id, r) for r in rows],
        "collection": {"code": repo.collection_code(user_id), "count": repo.count_shared(user_id)},
        "max": PAGES_MAX_PER_USER,
        "maxSources": SUMMARY_MAX_SOURCES,
        "extensions": sorted(SUMMARY_EXTENSIONS),
    }


@router.post("/pages")
async def create_page(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    mode: str = Form("files"),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    instructions: str = Form(""),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Takes the material, files it and starts the page."""
    if provider_id is not None and not feature_provider_choices.is_eligible("chat", provider_id):
        raise HTTPException(status_code=400, detail=t("summary.invalidProvider", locale))
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t(
            "file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))
    user_id = current_user.get("user_id", 0)
    if repo.count_pages(user_id) >= PAGES_MAX_PER_USER:
        raise HTTPException(status_code=409, detail=t("pages.tooMany", locale, max=PAGES_MAX_PER_USER))
    enforce_open_jobs(user_id, locale, "pages")
    enforce_tool_burst(user_id, "pages", locale)

    # The summary's reading and its messages, the material is the same.
    workspace_title = ""
    if mode == "module":
        from src.services import workspace_sources as arbeitsraum
        gelesen = await asyncio.to_thread(arbeitsraum.read_workspace,
            workspace_uuid, arbeitsraum.parse_uuids(source_uuids), user_id=user_id,
            locale=locale, hoechstens=SUMMARY_MAX_SOURCES, schluessel="summary")
        # Kept for the owner's info on the card, the workspace may be renamed or gone later.
        workspace_title = (db.get_aia_workspace(workspace_uuid) or {}).get("title") or ""
    else:
        gelesen = await sources.read_uploads(files, locale=locale, hoechstens=SUMMARY_MAX_SOURCES,
                                             schluessel="summary")

    enforce_quota(user_id, "pages", is_admin_user(current_user), locale)
    job_uuid = uuid.uuid4().hex
    await asyncio.to_thread(sources.save_sources, user_id, job_uuid, gelesen)
    create_counted_job(job_uuid, user_id, "pages", sources.label(gelesen), locale=locale)
    save_job_file(user_id, job_uuid, PARAMS_FILE, json.dumps({"provider_id": provider_id, "workspace": workspace_title}).encode())
    if instructions.strip():
        from src.services.job_files import write_job_text
        write_job_text(user_id, job_uuid, INSTRUCTIONS_FILE, instructions.strip()[:2000])

    from src.tasks.pages_tasks import run_pages
    task = run_pages.delay(job_uuid, provider_id)
    db.set_job_celery_task_id(job_uuid, task.id)
    logger.info("Pages {} eingereiht: {} Quelle(n), {} Zeichen", job_uuid[:8], len(gelesen),
                sum(len(q.text) for q in gelesen))
    return {"job_uuid": job_uuid, "status": "pending"}


@router.get("/pages/{job_uuid}")
def get_page(job_uuid: str, current_user: dict = Depends(get_current_user),
             locale: str = Depends(get_locale)):
    """The page as last saved, with the limits the editor enforces."""
    job = _own_job(job_uuid, current_user, locale)
    page, edited = load_page(job["user_id"], job_uuid)
    if job["status"] != "success" or page is None:
        raise HTTPException(status_code=409, detail=t("pages.notReady", locale))
    share = repo.get_share(job_uuid) or {}
    return {
        "job_uuid": job_uuid, "page": page, "edited": edited, "limits": schema.limits(),
        "shared": bool(share.get("enabled")), "code": share.get("code") if share.get("enabled") else None,
        "collection": repo.collection_code(job["user_id"]),
    }


@router.put("/pages/{job_uuid}")
async def save_page(job_uuid: str, request: Request, current_user: dict = Depends(get_current_user),
                    locale: str = Depends(get_locale)):
    """Stores the edited page, cut to the limits like the run's own page."""
    job = _own_job(job_uuid, current_user, locale)
    if job["status"] != "success":
        raise HTTPException(status_code=409, detail=t("pages.notReady", locale))
    body = await request.body()
    if len(body) > PAGES_MAX_JSON_BYTES:
        raise HTTPException(status_code=413, detail=t("pages.tooLarge", locale))
    try:
        page = schema.clean_page(json.loads(body))
    except ValueError:
        raise HTTPException(status_code=422, detail=t("pages.invalid", locale)) from None
    # Kept in the file, the card shows it as the date of the last change.
    page["saved_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    save_job_file(job["user_id"], job_uuid, USER_PAGE_FILE,
                  json.dumps(page, ensure_ascii=False).encode("utf-8"))
    return {"page": page}


@router.get("/pages/{job_uuid}/images/{name}")
def page_image(job_uuid: str, name: str, current_user: dict = Depends(get_current_user),
               locale: str = Depends(get_locale)):
    job = _own_job(job_uuid, current_user, locale)
    return _image(job["user_id"], job_uuid, name, locale)


class ShareBody(BaseModel):
    on: bool


@router.put("/pages/{job_uuid}/share")
def share_page(job_uuid: str, body: ShareBody, current_user: dict = Depends(get_current_user),
               locale: str = Depends(get_locale)):
    """Switches the link on or off, the code stays the same for the page's whole life."""
    job = _own_job(job_uuid, current_user, locale)
    if job["status"] != "success":
        raise HTTPException(status_code=409, detail=t("pages.notReady", locale))
    share = repo.set_share(job_uuid, job["user_id"], body.on)
    return {"shared": share["enabled"], "code": share["code"] if share["enabled"] else None,
            "collection": {"code": repo.collection_code(job["user_id"]),
                           "count": repo.count_shared(job["user_id"])}}


def _image(user_id: int, job_uuid: str, name: str, locale: str) -> Response:
    if not schema.IMAGE_NAME.match(name):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    try:
        data = get_job_file(user_id, job_uuid, name)
    except Exception:  # noqa: BLE001 - a missing picture is a 404, nothing more
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale)) from None
    art = _IMAGE_TYPES[name[name.rfind("."):]]
    return Response(content=data, media_type=art, headers={"Cache-Control": "private, max-age=86400"})


def _shared(code: str, locale: str) -> tuple[dict, dict]:
    row = repo.shared_page(code) if _CODE.match(code) else None
    page = load_page(row["user_id"], row["job_uuid"])[0] if row and row["status"] == "success" else None
    if not row or page is None:
        raise HTTPException(status_code=404, detail=t("pages.notShared", locale))
    return row, schema.for_viewers(page)


@shared_router.get("/pages/shared/{code}")
def shared_page(code: str, current_user: dict = Depends(get_current_user),
                locale: str = Depends(get_locale)):
    """A shared page for anyone logged in, hidden sections left out."""
    row, page = _shared(code, locale)
    return {"page": page, "owner": {"name": row["owner_name"], "code": row["collection_code"]},
            "limits": schema.limits()}


@shared_router.get("/pages/shared/{code}/images/{name}")
def shared_image(code: str, name: str, current_user: dict = Depends(get_current_user),
                 locale: str = Depends(get_locale)):
    row, page = _shared(code, locale)
    if name not in schema.images_of(page):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    return _image(row["user_id"], row["job_uuid"], name, locale)


@shared_router.get("/pages/collection/{code}")
def shared_collection(code: str, current_user: dict = Depends(get_current_user),
                      locale: str = Depends(get_locale)):
    """Every page one person shares, newest first, as cards."""
    daten = repo.collection(code) if _CODE.match(code) else None
    if not daten:
        raise HTTPException(status_code=404, detail=t("pages.collectionNotFound", locale))
    karten = []
    for row in daten["pages"]:
        page = load_page(daten["user_id"], row["job_uuid"])[0]
        if not page:
            continue
        sichtbar = schema.for_viewers(page)
        karten.append({"code": row["code"], "title": schema.title_of(sichtbar),
                       "image": schema.first_image(sichtbar),
                       "updated_at": page.get("saved_at") or _dt(row["completed_at"] or row["updated_at"])})
    # The owner gets the way back to their own pages, a reader has the logo.
    return {"owner": {"name": daten["owner_name"]}, "pages": karten,
            "own": daten["user_id"] == current_user.get("user_id", 0)}
