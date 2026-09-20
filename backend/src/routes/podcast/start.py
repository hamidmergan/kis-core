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
from src.features.podcast import source_text, store
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


def _als_quellen(quellen: list[tuple[str, list[dict]]]) -> list[dict]:
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


async def _aus_dateien(files: list[UploadFile], user_id: int, locale: str
                       ) -> tuple[list[tuple[str, list[dict]]], str]:
    """Reads every uploaded file once. Nothing of it outlives this request.

    The text goes into the job folder and is read into facts there. No module is created
    behind the person's back, and nothing is indexed: the facts phase reads the whole
    source, it never searches it.
    """
    quellen: list[tuple[str, list[dict]]] = []
    namen: list[str] = []
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
    return quellen, ", ".join(namen)


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
    # Only a real module ever does, an upload is gone again after this request.
    durchsuchbar: tuple[int | None, list[str]] = (None, [])
    # The job does not exist yet, so the numbers are recorded once it does.
    zahlen: dict = {"herkunft": mode, "anweisung": bool(einstellungen.instructions.strip())}

    with messe_vorab(zahlen):
        if mode == "files":
            _pruefe_gesamtgroesse(request, locale)
            quellen, label = await _aus_dateien(files, user_id, locale)
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
        # Only laid down here. Reading every source into facts costs one model call each
        # and belongs in the task, a web request must not wait for that.
        roh = _als_quellen(quellen)
        gesamt = "\n\n".join(q["content"] for q in roh)
        zahlen["zeichen_roh"] = len(gesamt)
        zahlen["budget"] = tool_context_budget()

    if not gesamt.strip():
        raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))

    # Checked first, charged second: a refused start costs no quota.
    _wacht(user_id, current_user, locale)

    job_uuid = uuid.uuid4().hex
    einstellungen.source_label = label
    # Sifted against the raw sources, the task narrows it again to the material it built.
    einstellungen.glossary = glossar.sift(einstellungen.glossary, gesamt)
    einstellungen.provider_id = einstellungen.persons[0].provider_id
    anzeige = label or (gesamt[:60].replace("\n", " ") + "…")
    db.create_job(job_uuid, user_id, "podcast", anzeige, locale=locale)
    notiere(user_id, job_uuid, "material", zahlen)
    store.save_material(user_id, job_uuid, roh, durchsuchbar[0], durchsuchbar[1], zahlen)
    store.save_params(user_id, job_uuid, einstellungen)

    from src.tasks.podcast_tasks import run_podcast_script

    task = run_podcast_script.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "script"})
    logger.info("Podcast {} gestartet, {} Quelle(n), {} Zeichen roh",
                job_uuid[:8], len(roh), len(gesamt))
    return {"job_uuid": job_uuid}
