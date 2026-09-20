# backend/src/features/praesentation/material.py
"""Material of a run: collecting it in the request, and handing a single slide its share.

Collecting means reading files and nothing more. What the sources say is pulled out of
them in the task, one model call per source, never in a web request.
"""

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
from src.services.facts.pool import Fact, fact_line, facts_block
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import pages_or_raise, validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

Quellen = list[tuple[str, list[dict]]]


async def aus_dateien(files: list[UploadFile], locale: str) -> tuple[Quellen, str]:
    """Reads every uploaded file once. Nothing of it outlives this request.

    The text goes into the job folder and is read into facts there. No workspace is
    created behind the person's back, and nothing is indexed: the facts phase reads a
    whole source, it never searches it.
    """
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


def als_quellen(quellen: Quellen) -> list[dict]:
    """The pieces of each file joined back into one text, that is what a read call gets.

    The number keeps the order the person chose, and names the source in a log line.
    """
    roh: list[dict] = []
    for i, (name, chunks) in enumerate(quellen, start=1):
        stuecke = [(c.get("content") or "").strip() for c in chunks]
        text = "\n".join(s for s in stuecke if s)
        if text:
            roh.append({"source_id": f"doc_{i:02d}", "filename": name, "content": text})
    return roh


def als_chunks(sources: list[dict]) -> Quellen:
    """The raw sources in the shape the older ways expect, one labelled pile of pieces each."""
    return [(q["filename"], source_text.to_pieces(q["content"])) for q in sources]


async def kontext(quellen: Quellen, instructions: str, workspace_id: int | None,
                  source_uuids: list[str] | None, fakten=None) -> str:
    """The older ways to a single block of material, the fallback once facts gave nothing."""
    return await instruction.build_context(quellen, instructions, workspace_id, source_uuids,
                                           {}, facts=fakten)


def ausschnitt(pool: list[Fact], schnappschuss: str, needles: list[str], limit: int) -> str:
    """The share of the run's material that matches these words.

    With a fact pool the matching facts win, so nothing is cut through the middle of a
    sentence any more. Without one the old character window on the snapshot remains.
    """
    if pool:
        return _aus_dem_vorrat(pool, needles, limit)
    if not schnappschuss.strip():
        return ""
    return folien.source_excerpt(schnappschuss, needles, limit)


def _aus_dem_vorrat(pool: list[Fact], needles: list[str], limit: int) -> str:
    """The facts that share a word with the needles, in the order of the pool.

    A fact that matches nothing stays out even when there would be room for it. This
    slide was asked for on one topic, and material beside that topic is what makes a
    slide drift. Only when nothing matches at all does the pool stand in, because
    material that does not fit still beats a slide with no ground under it.
    """
    woerter: set[str] = set()
    for nadel in needles:
        if nadel and nadel.strip():
            woerter |= folien.inhaltswoerter(nadel)
    treffer = [f for f in pool if woerter & folien.inhaltswoerter(f.fact)] if woerter else []
    if not treffer:
        logger.info("Präsentation: keine Fakten zu '{}', die Folie bekommt den Vorrat",
                    " ".join(n for n in needles if n)[:60])
    gewaehlt: list[Fact] = []
    laenge = 0
    for fakt in treffer or pool:
        kosten = len(fact_line(fakt, with_source=False)) + 1
        if gewaehlt and laenge + kosten > limit:
            break
        gewaehlt.append(fakt)
        laenge += kosten
    return facts_block(gewaehlt, limit)


async def fuer_folie(params: PraesentationParams, pool: list[Fact], schnappschuss: str,
                     needles: list[str]) -> str:
    """Material for one slide added later: the searched spots, or the run's own material.

    The material was gathered once for the whole deck, so a slide on a neighbouring topic
    may find nothing in it. Searching the workspace anew is the only way there.
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
    return ausschnitt(pool, schnappschuss, needles, PRAESENTATION_SLIDE_CONTEXT_CHARS)
