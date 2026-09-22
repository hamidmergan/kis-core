"""The first step: material and cast in, the script task out."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger
from pydantic import ValidationError

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.features.podcast import glossary as glossar
from src.features.podcast import store
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



def _pruefe_gesamtgroesse(request: Request, locale: str) -> None:
    """The size applies to all files together, not to each one on its own."""
    laenge = request.headers.get("content-length")
    grenze = max_upload_bytes()
    if laenge is not None and int(laenge) > grenze:
        raise HTTPException(status_code=413, detail=t(
            "podcast.uploadsTooLarge", locale, max=grenze // (1024 * 1024)))




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


async def _quellen_lesen(mode: str, files, locale: str) -> list:
    """Die Quellen eines Laufs. Nur Upload, ein Workspace wird nicht mehr angezapft."""
    from src.services import sources as quellen

    if mode != "files":
        raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))
    return await quellen.read_uploads(files, locale=locale,
                                      hoechstens=PODCAST_MAX_SOURCES, schluessel="podcast")


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
    user_id = current_user.get("user_id", 0)
    einstellungen = _pruefe_params(params, locale)
    if mode == "blank":
        return {"job_uuid": _leerer_auftrag(user_id, einstellungen, current_user, locale)}

    from src.services import sources as quellen

    _pruefe_gesamtgroesse(request, locale)
    gelesen = await _quellen_lesen(mode, files, locale)
    gesamt = quellen.as_block(gelesen)
    label = quellen.label(gelesen)
    if not gesamt.strip():
        raise HTTPException(status_code=422, detail=t("podcast.noContent", locale))
    zahlen: dict = {
        "herkunft": mode, "quellen": len(gelesen), "zeichen": len(gesamt),
        "stuecke": sum(len(q.stuecke) for q in gelesen),
        "anweisung": bool(einstellungen.instructions.strip()),
    }

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
    quellen.save_sources(user_id, job_uuid, gelesen)
    store.save_params(user_id, job_uuid, einstellungen)

    from src.tasks.podcast_tasks import run_podcast_script

    task = run_podcast_script.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "script"})
    logger.info("Podcast {} gestartet, {} Zeichen Material", job_uuid[:8], len(gesamt))
    return {"job_uuid": job_uuid}
