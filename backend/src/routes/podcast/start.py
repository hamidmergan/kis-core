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
from src.features.podcast import glossary as glossar
from src.features.podcast import instruction, source_store, source_text, store
from src.features.podcast.schemas import Line, PodcastParams
from src.i18n import get_locale, t
from src.limits import PODCAST_MAX_SOURCES
from src.quotas import enforce_quota
from src.services.job_statistik import messe_vorab, notiere
from src.services.open_jobs import enforce_open_jobs
from src.routes.podcast._shared import pruefe_params
from src.security.rate_limit import enforce_tool_burst
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import pages_or_raise, validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

router = APIRouter(tags=["podcast"])

_TOOLS = ["podcast"]


def _pruefe_params(roh: str, locale: str) -> PodcastParams:
    try:
        params = PodcastParams(**json.loads(roh))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        logger.warning("Podcast: Einstellungen unlesbar: {}", e)
        raise HTTPException(status_code=422, detail=t("podcast.badParams", locale)) from e
    return pruefe_params(params, locale)


def _wacht(user_id: int, current_user: dict, locale: str) -> None:
    """A person may have a few podcasts open, not a hundred."""
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "podcast", locale)
    enforce_quota(user_id, "podcast", is_admin_user(current_user), locale)


def _pruefe_anzahl(anzahl: int, locale: str) -> None:
    """More sources than this leave every single one with a useless share."""
    if anzahl > PODCAST_MAX_SOURCES:
        raise HTTPException(status_code=422, detail=t(
            "podcast.tooManySources", locale, max=PODCAST_MAX_SOURCES))


def _pruefe_gesamtgroesse(request: Request, locale: str) -> None:
    """The size applies to all files together, not to each one on its own."""
    laenge = request.headers.get("content-length")
    grenze = max_upload_bytes()
    if laenge is not None and int(laenge) > grenze:
        raise HTTPException(status_code=413, detail=t(
            "podcast.uploadsTooLarge", locale, max=grenze // (1024 * 1024)))


def _store_upload(user_id: int, name: str, pfad: str, ext: str, locale: str) -> str | None:
    """Files the upload for later runs, a failed filing never stops the podcast."""
    try:
        return source_store.put(user_id, name, pfad, ext, locale)
    except Exception as e:  # noqa: BLE001 — der Vorrat ist Beiwerk, nicht der Auftrag
        logger.warning("Podcast: {} nicht eingelagert: {}", name, e)
        return None


async def _aus_dateien(files: list[UploadFile], user_id: int, locale: str
                       ) -> tuple[list[tuple[str, list[dict]]], str, list[str]]:
    quellen: list[tuple[str, list[dict]]] = []
    namen: list[str] = []
    eingelagert: list[str] = []
    _pruefe_anzahl(len(files), locale)
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
            pages_or_raise(ext, ziel, locale)
            try:
                text = source_text.extract_file(ziel, ext)
            except Exception as e:  # noqa: BLE001 — eine kaputte Datei ist kein Serverfehler
                logger.warning("Podcast: {} nicht lesbar: {}", datei.filename, e)
                raise HTTPException(status_code=422, detail=t(
                    "podcast.fileUnreadable", locale, name=datei.filename or "?")) from e
            if text.strip():
                name = datei.filename or "?"
                quellen.append((name, source_text.to_pieces(text)))
                namen.append(name)
                # The run itself uses the text above, the embedding happens in the background.
                gelagert = _store_upload(user_id, name, ziel, ext, locale)
                if gelagert:
                    eingelagert.append(gelagert)
    return quellen, ", ".join(namen), eingelagert


def _leerer_auftrag(user_id: int, einstellungen: PodcastParams,
                    current_user: dict, locale: str) -> str:
    """The way without AI: a job, one empty contribution, straight back to the person."""
    _wacht(user_id, current_user, locale)
    job_uuid = uuid.uuid4().hex
    einstellungen.self_written = True
    # Nothing is written and nothing is rephrased here, so no glossary needs to travel along.
    einstellungen.glossary = {}
    einstellungen.provider_id = einstellungen.persons[0].provider_id
    einstellungen.source_label = t("podcast.selfWritten", locale)
    db.create_job(job_uuid, user_id, "podcast", einstellungen.source_label, locale=locale)
    notiere(user_id, job_uuid, "material",
            {"herkunft": "blank", "quellen": 0, "zeichen": 0, "anweisung": False})
    store.save_params(user_id, job_uuid, einstellungen)
    store.save_user_script(user_id, job_uuid, store.next_ids([Line()]))
    db.update_job_status(job_uuid, "awaiting_user", progress={"step": "script_done"})
    logger.info("Podcast {} leer gestartet", job_uuid[:8])
    return job_uuid


@router.post("/podcast/start")
async def start_podcast(
    request: Request,
    params: str = Form(...),
    mode: str = Form("files"),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Collects the material, writes it into the job folder and starts the script."""
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget

    user_id = current_user.get("user_id", 0)
    einstellungen = _pruefe_params(params, locale)
    if mode == "blank":
        return {"job_uuid": _leerer_auftrag(user_id, einstellungen, current_user, locale)}

    # Where the material also lies embedded, so a precise instruction can search it.
    durchsuchbar: tuple[int | None, list[str]] = (None, [])
    # The job does not exist yet, so the numbers are recorded once it does.
    zahlen: dict = {"herkunft": mode, "anweisung": bool(einstellungen.instructions.strip())}

    with messe_vorab(zahlen):
        if mode == "files":
            _pruefe_gesamtgroesse(request, locale)
            quellen, label, eingelagert = await _aus_dateien(files, user_id, locale)
            vorrat = source_store.store_of(user_id) if eingelagert else None
            if vorrat:
                durchsuchbar = (vorrat["id"], eingelagert)
            zahlen["eingelagert"] = len(eingelagert)
        elif mode == "module":
            try:
                uuids = json.loads(source_uuids)
            except json.JSONDecodeError:
                uuids = []
            if not workspace_uuid or not uuids:
                raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))
            _pruefe_anzahl(len(uuids), locale)
            quellen, label = source_text.from_module(workspace_uuid, uuids, user_id, locale)
            modul = db.get_aia_workspace(workspace_uuid)
            if modul:
                durchsuchbar = (modul["id"], uuids)
        else:
            raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))

        zahlen["quellen"] = len(quellen)
        quelle = await instruction.build_context(
            quellen, einstellungen.instructions, durchsuchbar[0], durchsuchbar[1], zahlen)
        zahlen["zeichen"] = len(quelle)
        zahlen["budget"] = tool_context_budget()

    if not quelle.strip():
        raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))

    # Checked first, charged second: a refused start costs no quota.
    _wacht(user_id, current_user, locale)

    job_uuid = uuid.uuid4().hex
    einstellungen.source_label = label
    einstellungen.instruction_unmatched = bool(zahlen.get("daneben"))
    einstellungen.glossary = glossar.sift(einstellungen.glossary, quelle)
    einstellungen.provider_id = einstellungen.persons[0].provider_id
    anzeige = label or (quelle[:60].replace("\n", " ") + "…")
    db.create_job(job_uuid, user_id, "podcast", anzeige, locale=locale)
    notiere(user_id, job_uuid, "material", zahlen)
    store.save_source(user_id, job_uuid, quelle)
    store.save_params(user_id, job_uuid, einstellungen)

    from src.tasks.podcast_tasks import run_podcast_script

    task = run_podcast_script.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "script"})
    logger.info("Podcast {} gestartet, {} Zeichen Material", job_uuid[:8], len(quelle))
    return {"job_uuid": job_uuid}
