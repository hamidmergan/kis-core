"""Kapitel im Quellenbereich: anlegen, umbenennen, verschieben, loeschen.

Kapitel sind reine Gliederung. Sie aendern nichts daran, was der Chat oder ein
Werkzeug zu sehen bekommt, das entscheidet weiterhin der Haken an der einzelnen
Datei. Deshalb gibt es hier auch keine Auswahl je Kapitel.

Alle Wege verlangen Verwaltungsrechte, also Eigentum oder Tutor. Studierende
sehen die Gliederung, aendern sie aber nicht.
"""

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
# Deckel gegen Versehen und Missbrauch. Wer mehr als hundert Kapitel braucht,
# braucht keine Gliederung, sondern einen zweiten Kursraum.
_MAX_CHAPTERS = 100
# Gleiche Regel wie beim Dateinamen: Pfadtrenner, Anfuehrungszeichen und
# Umbrueche wuerden Kopfzeilen und Prompts zerlegen.
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
    """Zwei gleich benannte Kapitel waeren in der Liste nicht zu unterscheiden."""
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
    """Kapitel laden und an den eigenen Kursraum binden.

    Ohne diese Pruefung koennte der Besitzer von Kursraum A ein Kapitel aus
    Kursraum B umbenennen oder loeschen. 404 statt 403, damit eine fremde uuid
    nicht von einer erfundenen zu unterscheiden ist.
    """
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
    # Am oberen oder unteren Rand passiert nichts. Das ist kein Fehler, die
    # Oberflaeche graut den Eintrag ohnehin aus.
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
    """Quelle einem Kapitel zuordnen. ``chapter_uuid: null`` heisst "Ohne Kapitel"."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    _load_workspace_source(source_uuid, workspace, locale)
    chapter_id = None
    if body.chapter_uuid:
        chapter = _load_workspace_chapter(body.chapter_uuid, workspace, locale)
        chapter_id = chapter["id"]
    db.set_aia_source_chapter(source_uuid, chapter_id)
    return {"uuid": source_uuid, "chapter_uuid": body.chapter_uuid or None}
