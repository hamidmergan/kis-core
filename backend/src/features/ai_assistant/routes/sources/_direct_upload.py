"""Direct upload of large files: the browser sends parts straight into the bucket.

The server only signs the parts and checks the joined file at the end, so a long
file costs this box neither bandwidth nor memory and leaves the page connection free.
"""
import json
import math
import os
import uuid
from urllib.parse import urlsplit

from fastapi import Request
from pydantic import BaseModel, Field

from src.security.rate_limit import check_upload_limit, record_upload
from src.storage import (
    S3_UPLOAD_PROXY,
    aia_source_key,
    delete_file,
    ensure_upload_cors,
    get_range,
    multipart_abort,
    multipart_complete,
    multipart_part_url,
    multipart_parts,
    multipart_start,
)
from src.utils.file_validation import validate_or_raise

from ._shared import (
    Path, APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    USE_S3,
    _require_workspace_manage,
    _require_source_capacity,
    _workspace_label,
    _enqueue_index_source,
    _ALLOWED_EXTENSIONS,
)

router = APIRouter(tags=["ki-assistent: sources"])

# Documents go this way too, the worker converts and counts pages after the upload.
_DIRECT_EXTENSIONS = set(_ALLOWED_EXTENSIONS)

# The smallest part S3 allows, a broken line loses little and progress moves often.
_PART_SIZE = 5 * 1024 * 1024
# A signed part stays valid this long, slow lines fetch new ones in small batches.
_PART_URL_SECONDS = 60 * 60
_MAX_URLS_PER_CALL = 20
# An open upload can be resumed this long, the bucket drops leftovers after a day too.
_SESSION_SECONDS = 24 * 60 * 60
_SESSION_PREFIX = "kis:aia:direct-upload:"

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

_CONTENT_TYPES = {
    ".mp3": "audio/mpeg", ".mp4": "video/mp4", ".wav": "audio/wav",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".webm": "video/webm",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _redis():
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def _save_session(token: str, session: dict) -> None:
    _redis().set(_SESSION_PREFIX + token, json.dumps(session), ex=_SESSION_SECONDS)


def _load_session(token: str, workspace_uuid: str, user_id: int, locale: str) -> dict:
    """Binds an open upload to its workspace and to the person who started it."""
    raw = _redis().get(_SESSION_PREFIX + token)
    session = json.loads(raw) if raw else None
    if not session or session["workspace_uuid"] != workspace_uuid or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail=t("ai.source.uploadExpired", locale))
    return session


def _drop_session(token: str) -> None:
    try:
        _redis().delete(_SESSION_PREFIX + token)
    except Exception as e:
        # The entry runs out by itself after _SESSION_SECONDS.
        logger.warning("Direct upload session {} not removed: {}", token, e)


def _part_count(size: int) -> int:
    return max(1, math.ceil(size / _PART_SIZE))


def _same_site_origin(request: Request) -> str:
    """The page's own origin, only when the browser's Origin matches the host it called."""
    origin = request.headers.get("origin") or ""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host = host.split(",")[0].strip()
    parts = urlsplit(origin)
    if parts.scheme in ("http", "https") and parts.netloc and parts.netloc == host:
        return f"{parts.scheme}://{parts.netloc}"
    return ""


def _duplicate_name(workspace: dict, filename: str) -> bool:
    key = filename.strip().lower()
    return any((s["filename"] or "").strip().lower() == key for s in db.get_aia_sources_by_workspace(workspace["id"]))


class DirectStart(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    size: int = Field(ge=0)


class PartNumbers(BaseModel):
    parts: list[int] = Field(min_length=1, max_length=_MAX_URLS_PER_CALL)


@router.post("/ai-assistant/workspaces/{workspace_uuid}/direct-uploads")
def start_direct_upload(
    workspace_uuid: str,
    body: DirectStart,
    request: Request,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Opens a direct upload, or answers direct False when the classic route fits better."""
    ext = Path(body.filename).suffix.lower()
    if not USE_S3 or ext not in _DIRECT_EXTENSIONS:
        return {"direct": False}

    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    check_upload_limit(current_user["user_id"], locale=locale)
    _require_source_capacity(db.get_aia_sources_by_workspace(workspace["id"]), locale)

    from src.services.tool_limits import max_upload_bytes
    if body.size == 0:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    max_bytes = max_upload_bytes()
    if body.size > max_bytes:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_bytes // (1024 * 1024)))
    if _duplicate_name(workspace, body.filename):
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.duplicateName", locale, name=body.filename, label=_workspace_label(locale)),
        )

    # Through the relay the browser stays on its own host and needs no CORS rule.
    if not S3_UPLOAD_PROXY:
        ensure_upload_cors(_same_site_origin(request))

    source_uuid = uuid.uuid4().hex
    # The file hangs off the owner, not off the person adding it.
    key = aia_source_key(workspace["user_id"], workspace_uuid, source_uuid, ext)
    upload_id = multipart_start(key, _CONTENT_TYPES.get(ext, ""))
    token = uuid.uuid4().hex
    _save_session(token, {
        "workspace_uuid": workspace_uuid,
        "user_id": current_user["user_id"],
        "source_uuid": source_uuid,
        "key": key,
        "upload_id": upload_id,
        "filename": body.filename,
        "ext": ext,
        "size": body.size,
    })
    logger.info("KI Tutor: direct upload {} opened for {} ({} bytes)", token, body.filename, body.size)
    return {
        "direct": True,
        "token": token,
        "part_size": _PART_SIZE,
        "part_count": _part_count(body.size),
        "uploaded": [],
    }


@router.get("/ai-assistant/workspaces/{workspace_uuid}/direct-uploads/{token}")
def direct_upload_status(
    workspace_uuid: str,
    token: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Which parts already arrived, so a broken upload goes on where it stopped."""
    _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    session = _load_session(token, workspace_uuid, current_user["user_id"], locale)
    parts = multipart_parts(session["key"], session["upload_id"])
    if parts is None:
        _drop_session(token)
        raise HTTPException(status_code=404, detail=t("ai.source.uploadExpired", locale))
    # Only full parts count, a cut-off last attempt is sent again.
    expected = {n: _PART_SIZE for n in range(1, _part_count(session["size"]))}
    expected[_part_count(session["size"])] = session["size"] - _PART_SIZE * (_part_count(session["size"]) - 1)
    done = sorted(p["PartNumber"] for p in parts if expected.get(p["PartNumber"]) == p["Size"])
    return {
        "direct": True,
        "token": token,
        "part_size": _PART_SIZE,
        "part_count": _part_count(session["size"]),
        "uploaded": done,
    }


@router.post("/ai-assistant/workspaces/{workspace_uuid}/direct-uploads/{token}/urls")
def direct_upload_urls(
    workspace_uuid: str,
    token: str,
    body: PartNumbers,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Signs a small batch of parts, each URL accepts exactly one PUT of that part."""
    _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    session = _load_session(token, workspace_uuid, current_user["user_id"], locale)
    count = _part_count(session["size"])
    if any(n < 1 or n > count for n in body.parts):
        raise HTTPException(status_code=400, detail=t("ai.source.uploadPartInvalid", locale))
    return {
        "urls": {
            str(n): multipart_part_url(session["key"], session["upload_id"], n, _PART_URL_SECONDS)
            for n in body.parts
        }
    }


@router.post("/ai-assistant/workspaces/{workspace_uuid}/direct-uploads/{token}/complete")
def complete_direct_upload(
    workspace_uuid: str,
    token: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Joins the parts, checks the result like a classic upload and registers the source."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    session = _load_session(token, workspace_uuid, current_user["user_id"], locale)
    key, upload_id, ext = session["key"], session["upload_id"], session["ext"]

    parts = multipart_parts(key, upload_id)
    if parts is None:
        _drop_session(token)
        raise HTTPException(status_code=404, detail=t("ai.source.uploadExpired", locale))
    count = _part_count(session["size"])
    numbers = sorted(p["PartNumber"] for p in parts)
    if numbers != list(range(1, count + 1)) or sum(p["Size"] for p in parts) != session["size"]:
        raise HTTPException(status_code=409, detail=t("ai.source.uploadIncomplete", locale))

    multipart_complete(key, upload_id, sorted(parts, key=lambda p: p["PartNumber"]))
    _drop_session(token)

    try:
        validate_or_raise(get_range(key, 0, 8192), ext, locale)
        # Someone may have added the same name or filled the room meanwhile.
        if _duplicate_name(workspace, session["filename"]):
            raise HTTPException(
                status_code=409,
                detail=t("ai.source.duplicateName", locale, name=session["filename"], label=_workspace_label(locale)),
            )
        _require_source_capacity(db.get_aia_sources_by_workspace(workspace["id"]), locale)
    except HTTPException:
        delete_file(key)
        raise

    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=session["source_uuid"],
        filename=session["filename"],
        file_path=key,
        file_type=ext.lstrip("."),
        source_url=None,
    )
    _enqueue_index_source(session["source_uuid"], current_user["user_id"], locale)
    record_upload(current_user["user_id"])
    logger.info(
        "KI Tutor: source {} ({}) uploaded directly to workspace {}",
        session["source_uuid"], session["filename"], workspace_uuid,
    )
    return {"uuid": session["source_uuid"], "filename": session["filename"], "status": "pending", "source_url": None}


@router.delete("/ai-assistant/workspaces/{workspace_uuid}/direct-uploads/{token}")
def abort_direct_upload(
    workspace_uuid: str,
    token: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Drops an open upload and every part already sent."""
    _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    session = _load_session(token, workspace_uuid, current_user["user_id"], locale)
    multipart_abort(session["key"], session["upload_id"])
    _drop_session(token)
    return {"ok": True}
