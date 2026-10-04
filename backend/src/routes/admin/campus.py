"""Settings, crawl status, documents and the place list of the campus assistant."""
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from src import storage
from src.dependencies_rbac import require_permission
from src.features.campus.repository import chats as chat_repo
from src.features.campus.repository import pages as page_repo
from src.features.campus.repository import places as place_repo
from src.features.campus.services import fetch as fetch_mod
from src.features.campus.services import settings as campus_settings
from src.features.campus.services.places_sync import parse_places
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_CAMPUS
from src.services import tool_limits
from src.utils.file_validation import validate_or_raise

router = APIRouter(prefix="/campus", tags=["admin: campus"])

_require = require_permission(PERM_SET_CAMPUS)
_DOC_EXTENSIONS = (".pdf", ".docx", ".pptx", ".md", ".txt")
_PLACES_KEY = "campus/places.json"


class SettingsBody(BaseModel):
    sitemap_url: Optional[str] = None
    url_include: Optional[str] = None
    url_exclude: Optional[str] = None
    map_url: Optional[str] = None
    places_url: Optional[str] = None
    retention_days: Optional[int] = None


def _overview() -> dict:
    cfg = campus_settings.read()
    stats = page_repo.page_stats()
    stats["places"] = place_repo.place_count()
    stats["feedback"] = chat_repo.feedback_stats()
    return {
        "settings": cfg.as_dict(),
        "status": campus_settings.crawl_status(),
        "stats": stats,
        "documents": [_document(d) for d in page_repo.list_pages(page_repo.KIND_DOCUMENT)],
    }


def _document(page: dict) -> dict:
    return {
        "id": page["id"], "filename": page["filename"], "title": page["title"], "status": page["status"],
        "chunk_count": page["chunk_count"], "error_message": page["error_message"],
        "created_at": page["created_at"].isoformat() if page.get("created_at") else None,
    }


@router.get("")
def get_campus(admin: dict = Depends(_require)):
    return _overview()


@router.patch("")
def update_campus(body: SettingsBody, admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    values = body.model_dump(exclude_unset=True)
    for key in ("sitemap_url", "places_url"):
        value = (values.get(key) or "").strip()
        if value and not fetch_mod.is_web_url(value):
            raise HTTPException(status_code=400, detail=t("campus.urlInvalid", locale))
    map_url = (values.get("map_url") or "").strip()
    if map_url and not map_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail=t("campus.urlInvalid", locale))
    campus_settings.write(values)
    return _overview()


@router.post("/crawl")
def start_crawl(admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    cfg = campus_settings.read()
    if not cfg.sitemap_url and not cfg.places_url and not storage.key_file_exists(_PLACES_KEY):
        raise HTTPException(status_code=400, detail=t("campus.notConfigured", locale))
    status = campus_settings.crawl_status()
    if status.get("running"):
        return status
    from src.features.campus.tasks import run_crawl
    run_crawl.delay()
    status = {"queued": True, "running": True}
    campus_settings.set_crawl_status(status)
    return status


@router.post("/documents")
async def upload_document(file: UploadFile = File(...), admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    if ext not in _DOC_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("campus.docTypeNotAllowed", locale))
    if any(d["filename"] == filename for d in page_repo.list_pages(page_repo.KIND_DOCUMENT)):
        raise HTTPException(status_code=409, detail=t("campus.docDuplicate", locale))
    limit = tool_limits.max_upload_bytes()
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=limit // (1024 * 1024)))
    validate_or_raise(data[:8192], ext, locale)
    stored = storage.save_key_file(f"campus/documents/{uuid.uuid4().hex}{ext}", data)
    page_id = page_repo.upsert_page(page_repo.KIND_DOCUMENT, None, title=Path(filename).stem, filename=filename, file_path=stored)
    from src.features.campus.tasks import run_index_document
    run_index_document.delay(page_id)
    return _document(page_repo.get_page(page_id))


@router.delete("/documents/{page_id}")
def delete_document(page_id: int, admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    page = page_repo.get_page(page_id)
    if page is None or page["kind"] != page_repo.KIND_DOCUMENT:
        raise HTTPException(status_code=404, detail=t("campus.documentNotFound", locale))
    if page.get("file_path"):
        try:
            storage.delete_file(page["file_path"])
        except Exception:
            pass
    page_repo.delete_page(page_id)
    return {"deleted": True}


@router.post("/places")
async def upload_places(file: UploadFile = File(...), admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    """A places.json of the campus map, indexed right away in the background."""
    data = await file.read(tool_limits.max_upload_bytes() + 1)
    try:
        places = parse_places(data)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail=t("campus.placesInvalid", locale))
    storage.save_key_file(_PLACES_KEY, data)
    from src.features.campus.tasks import run_sync_places_file
    run_sync_places_file.delay()
    return {"places": len(places)}
