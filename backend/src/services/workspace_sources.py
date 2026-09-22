"""The sources of a workspace, read the way an upload is read.

One single thing is borrowed from the assistant here: a workspace holds files, and the
database says which ones, who may see them and where they lie. Nothing else. No index,
no chunks, no retrieval, no budget. The stored file goes through the very same reader
an uploaded file goes through, so afterwards a source from a workspace and an uploaded
one are the same record and nothing downstream can tell them apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src import database as db
from src.i18n import t
from src.services.sources import check_total
from src.services.source_reading import (
    EXTENSIONS,
    NoReadableText,
    Source,
    from_text,
    read_file,
)

# A source counts as ready to use only in this state, the others have no text yet.
READY = "ready"


def _workspace_or_raise(workspace_uuid: str, user_id: int, locale: str) -> dict:
    """Who may take material out of a workspace.

    The rules are the ones the workspace itself uses. They are written out here rather
    than imported so that a service never reaches into the assistant, which means they
    have to be kept in step with ``_workspace_access`` by hand.
    """
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_student_enrolled(workspace["id"], user_id):
        if not workspace.get("is_active", True) and not db.is_workspace_tutor(workspace["id"], user_id):
            raise HTTPException(status_code=423, detail=t("workspace.inactive", locale))
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))


def parse_uuids(roh: str) -> list[str]:
    """The chosen source ids out of the form field, in the order the person picked."""
    try:
        werte = json.loads(roh or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(werte, list):
        return []
    gesehen: list[str] = []
    for wert in werte:
        if isinstance(wert, str) and wert and wert not in gesehen:
            gesehen.append(wert)
    return gesehen


def _transcript(source: dict, name: str) -> Source:
    """A source that is audio, video or a video link: its transcript is the document."""
    from src.storage import aia_transcript_key, file_exists, get_file

    schluessel = aia_transcript_key(source["file_path"])
    if not file_exists(schluessel):
        raise NoReadableText(name)
    return from_text(name, get_file(schluessel).decode("utf-8", errors="replace"))


def _document(source: dict, name: str) -> Source:
    """A source that is a real file: read exactly like an upload of the same file."""
    from src.storage import open_input_file

    with open_input_file(source["file_path"], suffix=Path(name).suffix.lower()) as pfad:
        return read_file(pfad, name)


def _read_one(source: dict) -> Source:
    """One workspace source to the canonical record.

    Whether a document or a transcript is read follows from the file name alone: a name
    the reader knows is read as a document, everything else must carry a transcript.
    That way a new media format on the assistant side needs no change here.
    """
    name = source["filename"] or source["uuid"]
    if Path(name).suffix.lower() in EXTENSIONS:
        return _document(source, name)
    return _transcript(source, name)


def read_workspace(workspace_uuid: str, source_uuids: list[str], *, user_id: int,
                   locale: str, hoechstens: int, schluessel: str) -> list[Source]:
    """The chosen sources of a workspace, in the order the person picked them."""
    if not workspace_uuid or not source_uuids:
        raise HTTPException(status_code=422, detail=t(f"{schluessel}.noContent", locale))
    if len(source_uuids) > hoechstens:
        raise HTTPException(status_code=422,
                            detail=t(f"{schluessel}.tooManySources", locale, max=hoechstens))
    workspace = _workspace_or_raise(workspace_uuid, user_id, locale)

    vorhanden = {q["uuid"]: q for q in db.get_aia_sources_by_workspace(workspace["id"])}
    gelesen: list[Source] = []
    for source_uuid in source_uuids:
        source = vorhanden.get(source_uuid)
        # An id from another workspace is not told apart from one that does not exist.
        if source is None:
            raise HTTPException(status_code=404,
                                detail=t(f"{schluessel}.sourceMissing", locale))
        if source["status"] != READY:
            raise HTTPException(status_code=409, detail=t(
                f"{schluessel}.sourceNotReady", locale, name=source["filename"]))
        name = source["filename"] or source_uuid
        try:
            gelesen.append(_read_one(source))
        except NoReadableText:
            raise HTTPException(status_code=422, detail=t(
                f"{schluessel}.sourceOnlyImages", locale, name=name)) from None
        except Exception as e:  # noqa: BLE001 - a broken stored file is no server fault
            logger.warning("Quelle '{}' aus Workspace {} nicht lesbar: {}",
                           name, workspace_uuid[:8], e)
            raise HTTPException(status_code=422, detail=t(
                f"{schluessel}.fileUnreadable", locale, name=name)) from e
    check_total(gelesen, locale, schluessel)
    logger.info("{}: {} Quelle(n) aus Workspace {}, {} Zeichen, {} Stueck(e)",
                schluessel, len(gelesen), workspace_uuid[:8],
                sum(len(q.text) for q in gelesen), sum(len(q.stuecke) for q in gelesen))
    return gelesen
