"""The first step: material and template in, the outline task out."""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import ValidationError

from src import database as db
from src.dependencies import get_current_user
from src.features.praesentation import store, vorlagen
from src.features.praesentation.schemas import LANGUAGES, PraesentationParams
from src.i18n import get_locale, t
from src.limits import PRAESENTATION_MAX_SOURCES
from src.services import feature_provider_choices
from src.services.open_jobs import create_counted_job, enforce_open_jobs
from src.tasks.praesentation_tasks import run_praesentation_outline

router = APIRouter(tags=["praesentation"])


def _pruefe_params(roh: str, locale: str) -> PraesentationParams:
    try:
        params = PraesentationParams(**json.loads(roh))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        logger.warning("Präsentation: Einstellungen unlesbar: {}", e)
        raise HTTPException(status_code=422, detail=t("praesentation.badParams", locale)) from e
    if params.language not in LANGUAGES:
        raise HTTPException(status_code=422, detail=t("praesentation.badParams", locale))
    if params.llm_provider_id is not None and not feature_provider_choices.is_eligible(
            "chat", params.llm_provider_id):
        raise HTTPException(status_code=400, detail=t("praesentation.invalidProvider", locale))
    return params


async def _quellen_lesen(mode: str, files, workspace_uuid: str, source_uuids: list[str],
                         user_id: int, locale: str) -> list:
    """A run's sources, uploaded or fetched from a workspace.

    Both paths end in the same record; the workspace supplies only the file, no index,
    sections or search.
    """
    from src.services import sources as quellen, workspace_sources as arbeitsraum

    if mode == "module":
        return await asyncio.to_thread(arbeitsraum.read_workspace,
            workspace_uuid, source_uuids, user_id=user_id, locale=locale,
            hoechstens=PRAESENTATION_MAX_SOURCES, schluessel="praesentation")
    if mode != "files":
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))
    return await quellen.read_uploads(files, locale=locale,
                                      hoechstens=PRAESENTATION_MAX_SOURCES,
                                      schluessel="praesentation")


@router.get("/praesentation/providers")
async def list_praesentation_providers(_user: dict = Depends(get_current_user)):
    """Reachable chat providers, the deck is written on the chat model."""
    return await feature_provider_choices.list_reachable_choices("chat")


@router.post("/praesentation/start")
async def start_praesentation(
    params: str = Form(...),
    mode: str = Form("files"),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user.get("user_id", 0)
    einstellungen = _pruefe_params(params, locale)
    if db.has_active_job_for_tool(user_id, ["praesentation"]):
        raise HTTPException(status_code=409, detail=t("praesentation.alreadyRunning", locale))
    enforce_open_jobs(user_id, locale, "praesentation")

    from src.services import sources as quellen, workspace_sources as arbeitsraum

    gewaehlt = arbeitsraum.parse_uuids(source_uuids) if mode == "module" else []
    gelesen = await _quellen_lesen(mode, files, workspace_uuid, gewaehlt, user_id, locale)
    text = quellen.as_block(gelesen)
    label = quellen.label(gelesen)
    if not text.strip():
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))

    vorlage_bytes, analyse, meta, fallback = await asyncio.to_thread(vorlagen.aufloesen, user_id, einstellungen.template_id)
    einstellungen.template_name = meta["name"]
    # A style changed in the first step wins, left untouched the template brings its own.
    if "style_text" not in einstellungen.model_fields_set:
        einstellungen.style_text = meta["style_text"]
    einstellungen.template_fallback = fallback
    einstellungen.source_label = label
    # Only a note of where the material came from, nothing reads back into the workspace.
    einstellungen.workspace_id = None
    einstellungen.source_uuids = gewaehlt
    if fallback:
        einstellungen.template_id = "thl"

    job_uuid = uuid.uuid4().hex
    create_counted_job(job_uuid, user_id, "praesentation", label or "Präsentation", locale=locale)
    def _ablegen() -> None:
        quellen.save_sources(user_id, job_uuid, gelesen)
        store.save_params(user_id, job_uuid, einstellungen)
        store.save_template(user_id, job_uuid, vorlage_bytes)
        store.save_template_meta(user_id, job_uuid, analyse)

    # Storage writes of up to 30 MB, off the loop so pages keep loading for everyone.
    await asyncio.to_thread(_ablegen)
    task = run_praesentation_outline.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "material"})
    logger.info("Präsentation {} gestartet, {} Zeichen Material",
                job_uuid[:8], len(text))
    return {"job_uuid": job_uuid}
