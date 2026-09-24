"""The sources of one run: from the upload into the job folder and back out again.

Reading a file is source_reading's business, this module is about the way in and the
way back: what a web request accepts, and what the job folder keeps.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from loguru import logger

from src.i18n import t
from src.limits import SOURCES_MAX_TOTAL_CHARS
from src.services.job_files import parse_job_json, read_job_text, write_job_text
from src.services.source_reading import EXTENSIONS, NoReadableText, Source, from_dict, read_file
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import pages_or_raise, validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

SOURCES_FILE = "sources.json"

# What all sources of a run may carry together, counted after reading.
MAX_TOTAL_CHARS = SOURCES_MAX_TOTAL_CHARS


def save_sources(user_id: int, job_uuid: str, sources: list[Source]) -> None:
    """The read sources into the job folder, the canonical text of this run."""
    write_job_text(user_id, job_uuid, SOURCES_FILE,
                   json.dumps([q.as_dict() for q in sources], ensure_ascii=False))


def load_sources(user_id: int, job_uuid: str) -> list[Source]:
    """The sources back out, an empty list when the file is missing or damaged."""
    roh = parse_job_json(job_uuid, SOURCES_FILE,
                         read_job_text(user_id, job_uuid, SOURCES_FILE), None)
    return [from_dict(eintrag) for eintrag in roh or [] if isinstance(eintrag, dict)]


def as_block(sources: list[Source]) -> str:
    """Every source as one text, each under its file name.

    For the tools that want one block instead of a list. The name travels with it so
    the model can tell two documents apart, nothing more.
    """
    return "\n\n".join(f"# {q.dateiname}\n{q.text}" for q in sources if q.text.strip())


def label(sources: list[Source]) -> str:
    """What the job list calls this run."""
    return ", ".join(q.dateiname for q in sources)


def _check_count(anzahl: int, hoechstens: int, locale: str, schluessel: str) -> None:
    if anzahl < 1:
        raise HTTPException(status_code=422, detail=t(f"{schluessel}.noContent", locale))
    if anzahl > hoechstens:
        raise HTTPException(status_code=422,
                            detail=t(f"{schluessel}.tooManySources", locale, max=hoechstens))


def _zahl(n: int) -> str:
    """A number the way it is written in German, with a dot every three digits."""
    return f"{n:,}".replace(",", ".")


def check_total(sources: list[Source], locale: str, schluessel: str) -> None:
    """Refuses material that is too long in sum, before any model has been paid for it."""
    zeichen = sum(len(q.text) for q in sources)
    if zeichen > MAX_TOTAL_CHARS:
        raise HTTPException(status_code=422, detail=t(
            f"{schluessel}.materialTooLarge", locale,
            chars=_zahl(zeichen), max=_zahl(MAX_TOTAL_CHARS)))


async def _read_upload(datei: UploadFile, tmpdir: str, locale: str, schluessel: str) -> Source:
    """One uploaded file through every check and the reader."""
    name = datei.filename or "?"
    ext = Path(name).suffix.lower()
    if ext not in EXTENSIONS:
        raise HTTPException(status_code=400, detail=t(
            f"{schluessel}.unsupportedFormat", locale, formats=", ".join(EXTENSIONS)))
    ziel = os.path.join(tmpdir, f"{uuid.uuid4().hex}{ext}")
    groesse, kopf = await stream_upload_to_path(datei, ziel, max_upload_bytes(), locale)
    if not groesse:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    validate_or_raise(kopf, ext, locale)
    pages_or_raise(ext, ziel, locale)
    try:
        return read_file(ziel, name)
    except NoReadableText:
        raise HTTPException(status_code=422, detail=t(
            f"{schluessel}.sourceOnlyImages", locale, name=name)) from None
    except Exception as e:  # noqa: BLE001 - a broken file is no server fault
        logger.warning("Quelle '{}' nicht lesbar: {}", name, e)
        raise HTTPException(status_code=422, detail=t(
            f"{schluessel}.fileUnreadable", locale, name=name)) from e


async def measure_upload(datei: UploadFile, *, locale: str, schluessel: str) -> int:
    """The characters one file brings, counted exactly as the start will count them."""
    with tempfile.TemporaryDirectory(prefix="messen_") as tmpdir:
        return len((await _read_upload(datei, tmpdir, locale, schluessel)).text)


async def read_uploads(files: list[UploadFile], *, locale: str, hoechstens: int,
                       schluessel: str) -> list[Source]:
    """Every uploaded file read once. The file itself does not outlive this request.

    What survives is the canonical text with its pieces, nothing is indexed and no
    workspace is created behind the person's back.
    """
    _check_count(len(files or []), hoechstens, locale, schluessel)
    gelesen: list[Source] = []
    with tempfile.TemporaryDirectory(prefix="quellen_") as tmpdir:
        for datei in files:
            gelesen.append(await _read_upload(datei, tmpdir, locale, schluessel))
    check_total(gelesen, locale, schluessel)
    zeichen = sum(len(q.text) for q in gelesen)
    logger.info("{}: {} Quelle(n) gelesen, {} Zeichen, {} Stueck(e)",
                schluessel, len(gelesen), zeichen, sum(len(q.stuecke) for q in gelesen))
    return gelesen
