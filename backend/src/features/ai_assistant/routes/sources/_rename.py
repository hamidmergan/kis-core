"""Eine Quelle umbenennen.

Bearbeitet wird nur der Namensteil, die Endung bleibt fest. Das ist kein
Schoenheitsfehler, sondern die tragende Entscheidung: an mehreren Stellen wird
der Dateityp aus der Endung von ``filename`` gelesen, im Chat, in der PDF-Suche,
beim Ausliefern der Datei und im Frontend beim Symbol und beim Viewer. Ein Name
ohne Endung wuerde sie alle blind machen.
"""

from pydantic import BaseModel

from ._shared import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    db,
    get_current_user,
    get_locale,
    logger,
    t,
    _load_workspace_source,
    _require_workspace_manage,
    _workspace_label,
)
from src.features.ai_assistant.repository.source_rename import rename_aia_source

router = APIRouter(tags=["ki-assistent: sources"])

_MAX_NAME_LEN = 200
# Pfadtrenner koennten im Download-Header eine Verzeichnisebene vortaeuschen,
# Anfuehrungszeichen und Umbrueche wuerden ihn und jeden Prompt zerlegen.
_FORBIDDEN = set('/\\"\r\n\t')


class RenameSourceBody(BaseModel):
    name: str


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}")
def rename_source(
    workspace_uuid: str,
    source_uuid: str,
    body: RenameSourceBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    # Bindet die Quelle an den eigenen Kursraum. Ohne diese Pruefung koennte der
    # Besitzer von Kursraum A eine Quelle aus Kursraum B umbenennen.
    source = _load_workspace_source(source_uuid, workspace, locale)

    suffix = Path(source["filename"]).suffix
    stem = "".join(c for c in body.name if c not in _FORBIDDEN and c.isprintable()).strip()
    # Wer die Endung mittippt, soll nicht "name.pdf.pdf" bekommen.
    if suffix and stem.lower().endswith(suffix.lower()):
        stem = stem[: -len(suffix)].strip()
    if not stem:
        raise HTTPException(status_code=400, detail=t("ai.source.nameEmpty", locale))
    if len(stem) > _MAX_NAME_LEN:
        raise HTTPException(
            status_code=400,
            detail=t("ai.source.nameTooLong", locale, max=_MAX_NAME_LEN),
        )

    new_filename = f"{stem}{suffix}"
    # Gleiche Regel wie beim Hochladen: ein Name je Kursraum, Gross- und
    # Kleinschreibung zaehlt nicht. Die eigene Zeile ist ausgenommen, sonst
    # scheiterte schon das Umstellen der Schreibweise.
    taken = {
        (s["filename"] or "").strip().lower()
        for s in db.get_aia_sources_by_workspace(workspace["id"])
        if s["uuid"] != source_uuid
    }
    if new_filename.strip().lower() in taken:
        raise HTTPException(
            status_code=409,
            detail=t(
                "ai.source.duplicateName", locale,
                name=new_filename, label=_workspace_label(locale),
            ),
        )

    rename_aia_source(source_uuid, new_filename)
    logger.info("KI Tutor: source {} renamed to '{}'", source_uuid, new_filename)
    return {"filename": new_filename}
