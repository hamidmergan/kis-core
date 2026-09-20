"""Permission checks and file handling for a course room."""

from fastapi import HTTPException
from loguru import logger

from src import database as db
from src.i18n import DEFAULT_LOCALE, t
from src.storage import delete_aia_workspace_folder, save_aia_source_from_path


def _visible_workspace(workspace_uuid: str, locale: str) -> dict:
    """The course room behind this uuid, an unknown one is a 404 for every route."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    return workspace


def _require_workspace_owner(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Owner only: deleting and granting tutor rights."""
    workspace = _visible_workspace(workspace_uuid, locale)
    if workspace["user_id"] != user_id:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace


def _require_workspace_manage(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allows owner or tutor, for everything that changes a course room."""
    workspace = _visible_workspace(workspace_uuid, locale)
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_workspace_tutor(workspace["id"], user_id):
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))


def _require_workspace_access(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allows owner or enrolled people, an inactive course room answers with 423."""
    workspace = _visible_workspace(workspace_uuid, locale)
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_student_enrolled(workspace["id"], user_id):
        if not workspace.get("is_active", True) and not db.is_workspace_tutor(workspace["id"], user_id):
            raise HTTPException(status_code=423, detail=t("workspace.inactive", locale))
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))


def _save_source_file_path(user_id: int, workspace_uuid: str, source_uuid: str, ext: str, local_path: str) -> str:
    """Stores an uploaded source, streaming from disk."""
    return save_aia_source_from_path(user_id, workspace_uuid, source_uuid, ext, local_path)


def _delete_workspace_files(workspace: dict) -> None:
    """Removes the course room folder as a whole, derived files included."""
    try:
        removed = delete_aia_workspace_folder(workspace["user_id"], workspace["uuid"])
        logger.info("KI Tutor: removed {} files for workspace {}", removed, workspace["uuid"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete files for workspace {}: {}", workspace["uuid"], e)


def _resolve_source_ids(
    workspace: dict, source_uuids: list[str], max_count: int | None = None,
    locale: str = DEFAULT_LOCALE,
) -> list[int]:
    """Resolve source UUIDs to DB IDs, without a cap unless one is asked for."""
    if max_count is not None and len(source_uuids) > max_count:
        raise HTTPException(status_code=400, detail=t("ai.source.maxAllowed", locale, max=max_count))
    ids = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source and source["workspace_id"] == workspace["id"] and source["status"] == "ready":
            ids.append(source["id"])
    if not ids:
        raise HTTPException(status_code=400, detail=t("ai.source.noValidSelected", locale))
    return ids
