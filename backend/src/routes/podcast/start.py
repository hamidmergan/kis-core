"""The first step: material and cast in, the script task out."""

import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger
from pydantic import ValidationError

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.features.podcast import source_text, store
from src.features.podcast.schemas import LANGUAGES, LENGTH_WORDS, ROLES, STYLES, PodcastParams
from src.i18n import get_locale, t
from src.limits import MAX_QUEUED_PODCAST_JOBS, PODCAST_MAX_SOURCE_CHARS
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

router = APIRouter(tags=["podcast"])

_TOOLS = ["podcast"]


def _pruefe_params(roh: str, locale: str) -> PodcastParams:
    try:
        params = PodcastParams(**json.loads(roh))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        logger.warning("Podcast: Einstellungen unlesbar: {}", e)
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale)) from e
    if not 1 <= len(params.persons) <= 4:
        raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
    if params.language not in LANGUAGES or params.length not in LENGTH_WORDS or params.style not in STYLES:
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale))
    for person in params.persons:
        if person.role not in ROLES or not person.voice_id or person.provider_id <= 0:
            raise HTTPException(status_code=422, detail=t("podcast.badCast", locale))
    return params


def _wacht(user_id: int, current_user: dict, locale: str) -> None:
    """A person may have a few podcasts open, not a hundred."""
    if db.count_all_jobs_for_tool(user_id, _TOOLS) >= MAX_QUEUED_PODCAST_JOBS:
        raise HTTPException(status_code=409,
                            detail=t("podcast.queueFull", locale, max=MAX_QUEUED_PODCAST_JOBS))
    enforce_tool_burst(user_id, "podcast", locale)
    enforce_quota(user_id, "podcast", is_admin_user(current_user), locale)


async def _aus_dateien(files: list[UploadFile], locale: str) -> tuple[str, str]:
    teile: list[str] = []
    namen: list[str] = []
    with tempfile.TemporaryDirectory(prefix="podcast_upload_") as tmpdir:
        for datei in files:
            ext = Path(datei.filename or "").suffix.lower()
            if ext not in source_text.PODCAST_EXTENSIONS:
                raise HTTPException(status_code=400, detail=t(
                    "podcast.unsupportedFormat", locale,
                    formats=", ".join(source_text.PODCAST_EXTENSIONS)))
            ziel = os.path.join(tmpdir, f"{uuid.uuid4().hex}{ext}")
            groesse, kopf = await stream_upload_to_path(datei, ziel, max_upload_bytes(), locale)
            if not groesse:
                raise HTTPException(status_code=400, detail=t("file.empty", locale))
            validate_or_raise(kopf, ext, locale)
            try:
                text = source_text.extract_file(ziel, ext)
            except Exception as e:  # noqa: BLE001 — eine kaputte Datei ist kein Serverfehler
                logger.warning("Podcast: {} nicht lesbar: {}", datei.filename, e)
                raise HTTPException(status_code=422, detail=t(
                    "podcast.fileUnreadable", locale, name=datei.filename or "?")) from e
            if text.strip():
                teile.append(f"# {datei.filename}\n{text.strip()}")
                namen.append(datei.filename or "?")
    return "\n\n".join(teile), ", ".join(namen)


@router.post("/podcast/start")
async def start_podcast(
    request: Request,
    params: str = Form(...),
    mode: str = Form("text"),
    text: str = Form(""),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Collects the material, writes it into the job folder and starts the script."""
    user_id = current_user.get("user_id", 0)
    einstellungen = _pruefe_params(params, locale)

    if mode == "files":
        quelle, label = await _aus_dateien(files, locale)
    elif mode == "module":
        try:
            uuids = json.loads(source_uuids)
        except json.JSONDecodeError:
            uuids = []
        if not workspace_uuid or not uuids:
            raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))
        quelle, label = source_text.from_module(workspace_uuid, uuids, user_id, locale)
    else:
        quelle, label = text.strip(), ""

    if not quelle.strip():
        raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))
    quelle = source_text.shorten(quelle, PODCAST_MAX_SOURCE_CHARS)

    # Checked first, charged second: a refused start costs no quota.
    _wacht(user_id, current_user, locale)

    job_uuid = uuid.uuid4().hex
    einstellungen.source_label = label
    einstellungen.provider_id = einstellungen.persons[0].provider_id
    anzeige = label or (quelle[:60].replace("\n", " ") + "…")
    db.create_job(job_uuid, user_id, "podcast", anzeige, locale=locale)
    store.save_source(user_id, job_uuid, quelle)
    store.save_params(user_id, job_uuid, einstellungen)

    from src.tasks.podcast_tasks import run_podcast_script

    task = run_podcast_script.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "script"})
    logger.info("Podcast {} gestartet, {} Zeichen Material", job_uuid[:8], len(quelle))
    return {"job_uuid": job_uuid}
