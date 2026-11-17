"""Sources that arrived through the shared direct upload: the browser sent them in parts.

This module registers the AI assistant's rule with the upload core and turns a finished
upload into a source. The worker converts documents and counts pages afterwards.
"""
import uuid

from fastapi import Depends
from pydantic import BaseModel, Field

from src.services import direct_upload
from src.services.tool_limits import max_upload_bytes
from src.storage import aia_source_key, copy_key

from ._shared import (
    APIRouter, HTTPException, db, logger, t,
    get_current_user, get_locale,
    _ALLOWED_EXTENSIONS,
    _enqueue_index_source,
    _require_source_capacity,
    _require_workspace_manage,
    _workspace_label,
)

router = APIRouter(tags=["ki-assistent: sources"])
TOOL = "aia"


def _duplicate_name(workspace: dict, filename: str) -> bool:
    key = filename.strip().lower()
    return any((s["filename"] or "").strip().lower() == key for s in db.get_aia_sources_by_workspace(workspace["id"]))


def _check_room(workspace: dict, filename: str, locale: str) -> None:
    """The room still has space and no source of the same name, checked at start and at the end."""
    _require_source_capacity(db.get_aia_sources_by_workspace(workspace["id"]), locale)
    if _duplicate_name(workspace, filename):
        raise HTTPException(
            status_code=409,
            detail=t("ai.source.duplicateName", locale, name=filename, label=_workspace_label(locale)),
        )


def _precheck(user: dict, context: dict, filename: str, size: int, locale: str) -> None:
    """Only someone who may change this course room uploads into it."""
    workspace = _require_workspace_manage(context.get("workspace_uuid", ""), user["user_id"], locale=locale)
    _check_room(workspace, filename, locale)


direct_upload.register(TOOL, direct_upload.UploadRule(
    _ALLOWED_EXTENSIONS, lambda: max_upload_bytes(), precheck=_precheck))


class FromUpload(BaseModel):
    upload_token: str = Field(min_length=1, max_length=64)


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/from-upload")
def source_from_upload(
    workspace_uuid: str,
    body: FromUpload,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Makes a source of a finished direct upload and queues it for reading."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_manage(workspace_uuid, user_id, locale=locale)
    session = direct_upload.take(body.upload_token, TOOL, user_id, locale)
    if session["context"].get("workspace_uuid") != workspace_uuid:
        raise HTTPException(status_code=404, detail=t("ai.source.uploadExpired", locale))
    # Someone may have added the same name or filled the room meanwhile.
    _check_room(workspace, session["filename"], locale)

    source_uuid = uuid.uuid4().hex
    # The file hangs off the owner, not off the person adding it.
    key = aia_source_key(workspace["user_id"], workspace_uuid, source_uuid, session["ext"])
    copy_key(session["key"], key)
    direct_upload.release(body.upload_token, session)

    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=source_uuid,
        filename=session["filename"],
        file_path=key,
        file_type=session["ext"].lstrip("."),
        source_url=None,
    )
    _enqueue_index_source(source_uuid, user_id, locale)
    logger.info("KI Tutor: source {} ({}) uploaded directly to workspace {}", source_uuid, session["filename"], workspace_uuid)
    return {"uuid": source_uuid, "filename": session["filename"], "status": "pending", "source_url": None}
