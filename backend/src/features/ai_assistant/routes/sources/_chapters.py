"""Create, rename, move and delete chapters and order the sources in them, pure structure."""

import uuid as uuid_lib

from pydantic import BaseModel

from ._shared import (
    APIRouter,
    Depends,
    HTTPException,
    Optional,
    db,
    get_current_user,
    get_locale,
    logger,
    t,
    _load_workspace_source,
    _require_workspace_manage,
)

router = APIRouter(tags=["ki-assistent: chapters"])

_MAX_NAME_LEN = 100
# Cap against accidents, more than a hundred chapters is no longer structure.
_MAX_CHAPTERS = 100
# Path separators, quotes and line breaks would break header lines apart.
_FORBIDDEN = set('/\\"\r\n\t')


class ChapterBody(BaseModel):
    name: str


class MoveChapterBody(BaseModel):
    direction: str


class SetChapterBody(BaseModel):
    chapter_uuid: Optional[str] = None


def _clean_name(raw: str, locale: str) -> str:
    name = "".join(c for c in raw if c not in _FORBIDDEN and c.isprintable()).strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("ai.chapter.nameEmpty", locale))
    if len(name) > _MAX_NAME_LEN:
        raise HTTPException(
            status_code=400,
            detail=t("ai.chapter.nameTooLong", locale, max=_MAX_NAME_LEN),
        )
    return name


def _reject_duplicate(name: str, workspace_id: int, locale: str, skip_uuid: str | None = None) -> None:
    """Two chapters of the same name could not be told apart in the list."""
    taken = {
        (c["name"] or "").strip().lower()
        for c in db.get_aia_chapters_by_workspace(workspace_id)
        if c["uuid"] != skip_uuid
    }
    if name.strip().lower() in taken:
        raise HTTPException(
            status_code=409,
            detail=t("ai.chapter.duplicateName", locale, name=name),
        )


def _load_workspace_chapter(chapter_uuid: str, workspace: dict, locale: str) -> dict:
    """Loads a chapter and binds it to your own course room, otherwise 404."""
    chapter = db.get_aia_chapter(chapter_uuid)
    if not chapter or chapter["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("ai.chapter.notFound", locale))
    return chapter


def _as_dict(chapter: dict) -> dict:
    return {
        "uuid": chapter["uuid"],
        "name": chapter["name"],
        "position": chapter["position"],
    }


@router.post("/ai-assistant/workspaces/{workspace_uuid}/chapters")
def create_chapter(
    workspace_uuid: str,
    body: ChapterBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    name = _clean_name(body.name, locale)
    if db.count_aia_chapters(workspace["id"]) >= _MAX_CHAPTERS:
        raise HTTPException(
            status_code=400,
            detail=t("ai.chapter.tooMany", locale, max=_MAX_CHAPTERS),
        )
    _reject_duplicate(name, workspace["id"], locale)
    chapter = db.create_aia_chapter(workspace["id"], uuid_lib.uuid4().hex, name)
    logger.info("KI Tutor: chapter '{}' created in workspace {}", name, workspace_uuid)
    return _as_dict(chapter)


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/chapters/{chapter_uuid}")
def rename_chapter(
    workspace_uuid: str,
    chapter_uuid: str,
    body: ChapterBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    chapter = _load_workspace_chapter(chapter_uuid, workspace, locale)
    name = _clean_name(body.name, locale)
    _reject_duplicate(name, workspace["id"], locale, skip_uuid=chapter_uuid)
    db.rename_aia_chapter(chapter_uuid, name)
    return {"uuid": chapter_uuid, "name": name, "position": chapter["position"]}


@router.delete("/ai-assistant/workspaces/{workspace_uuid}/chapters/{chapter_uuid}")
def delete_chapter(
    workspace_uuid: str,
    chapter_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    _load_workspace_chapter(chapter_uuid, workspace, locale)
    db.delete_aia_chapter(chapter_uuid)
    logger.info("KI Tutor: chapter {} deleted in workspace {}", chapter_uuid, workspace_uuid)
    return {"ok": True}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/chapters/{chapter_uuid}/move")
def move_chapter(
    workspace_uuid: str,
    chapter_uuid: str,
    body: MoveChapterBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    _load_workspace_chapter(chapter_uuid, workspace, locale)
    if body.direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail=t("ai.chapter.badDirection", locale))
    # Nothing happens at the edge, the interface greys the entry out anyway.
    db.move_aia_chapter(chapter_uuid, body.direction)
    return {
        "chapters": [_as_dict(c) for c in db.get_aia_chapters_by_workspace(workspace["id"])]
    }


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/chapter")
def set_source_chapter(
    workspace_uuid: str,
    source_uuid: str,
    body: SetChapterBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Assign a source to a chapter, ``chapter_uuid: null`` means no chapter."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    _load_workspace_source(source_uuid, workspace, locale)
    chapter_id = None
    if body.chapter_uuid:
        chapter = _load_workspace_chapter(body.chapter_uuid, workspace, locale)
        chapter_id = chapter["id"]
    db.set_aia_source_chapter(source_uuid, chapter_id)
    return {
        "uuid": source_uuid,
        "chapter_uuid": body.chapter_uuid or None,
        "order": _source_order(workspace["id"]),
    }


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/move")
def move_source(
    workspace_uuid: str,
    source_uuid: str,
    body: MoveChapterBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Move a source one slot up or down within its chapter."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    _load_workspace_source(source_uuid, workspace, locale)
    if body.direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail=t("ai.chapter.badDirection", locale))
    db.move_aia_source(source_uuid, body.direction)
    return {"order": _source_order(workspace["id"])}


def _source_order(workspace_id: int) -> list[str]:
    """Uuids of all sources in list order, the interface sorts by it."""
    return [s["uuid"] for s in db.get_aia_sources_by_workspace(workspace_id)]
