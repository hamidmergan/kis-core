# backend/src/features/praesentation/material.py
"""Material of a run: uploads or workspace sources, cut to the tool budget the podcast uses."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from loguru import logger

from src import database as db
from src.features.podcast import instruction, source_text
from src.features.praesentation import folien
from src.features.praesentation.schemas import PraesentationParams
from src.i18n import t
from src.limits import PRAESENTATION_MAX_SOURCES, PRAESENTATION_SLIDE_CONTEXT_CHARS
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import pages_or_raise, validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

Quellen = list[tuple[str, list[dict]]]


async def aus_dateien(files: list[UploadFile], locale: str) -> tuple[Quellen, str]:
    if len(files) > PRAESENTATION_MAX_SOURCES:
        raise HTTPException(status_code=422, detail=t("praesentation.tooManySources", locale,
                                                      max=PRAESENTATION_MAX_SOURCES))
    quellen: Quellen = []
    namen: list[str] = []
    with tempfile.TemporaryDirectory(prefix="praesentation_upload_") as tmpdir:
        for datei in files:
            name = Path(datei.filename or "").stem
            ext = Path(datei.filename or "").suffix.lower()
            if ext not in source_text.PODCAST_EXTENSIONS:
                raise HTTPException(status_code=400, detail=t(
                    "praesentation.unsupportedFormat", locale, formats=", ".join(source_text.PODCAST_EXTENSIONS)))
            ziel = os.path.join(tmpdir, f"{uuid.uuid4().hex}{ext}")
            groesse, kopf = await stream_upload_to_path(datei, ziel, max_upload_bytes(), locale)
            if not groesse:
                raise HTTPException(status_code=400, detail=t("file.empty", locale))
            validate_or_raise(kopf, ext, locale)
            pages_or_raise(ext, ziel, locale)
            try:
                text = source_text.extract_file(ziel, ext)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=t("praesentation.unreadable", locale, name=name)) from exc
            if text.strip():
                quellen.append((name, source_text.to_pieces(text)))
                namen.append(name)
    return quellen, ", ".join(namen)[:120]


def aus_workspace(workspace_uuid: str, source_uuids: list[str], user_id: int, locale: str
                  ) -> tuple[Quellen, str, dict | None]:
    if len(source_uuids) > PRAESENTATION_MAX_SOURCES:
        raise HTTPException(status_code=422, detail=t("praesentation.tooManySources", locale,
                                                      max=PRAESENTATION_MAX_SOURCES))
    quellen, label = source_text.from_module(workspace_uuid, source_uuids, user_id, locale)
    return quellen, label, db.get_aia_workspace(workspace_uuid)


async def kontext(quellen: Quellen, instructions: str, workspace_id: int | None,
                  source_uuids: list[str] | None) -> str:
    return await instruction.build_context(quellen, instructions, workspace_id, source_uuids, {})


async def fuer_folie(params: PraesentationParams, schnappschuss: str, needles: list[str]) -> str:
    """Material for one slide added later: the searched spots, or a cut-out of the run's snapshot.

    The snapshot was built once for the whole deck, so a slide on a neighbouring
    topic may find nothing in it. Searching the workspace anew is the only way there.
    """
    frage = " ".join(n.strip() for n in needles if n and n.strip())
    if frage and params.workspace_id and params.source_uuids:
        try:
            gefunden = await instruction.search_context(
                params.workspace_id, params.source_uuids, frage, PRAESENTATION_SLIDE_CONTEXT_CHARS)
        except Exception as e:  # noqa: BLE001 - a failed search must not cost the slide
            logger.warning("Präsentation: gezielte Suche für eine Folie gescheitert: {}", e)
            gefunden = ""
        if gefunden.strip():
            return gefunden
    return folien.source_excerpt(schnappschuss, needles, PRAESENTATION_SLIDE_CONTEXT_CHARS)
