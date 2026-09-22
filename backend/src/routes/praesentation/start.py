"""The first step: material and template in, the outline task out."""

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
    return params


async def _quellen_lesen(mode: str, files, locale: str) -> list:
    """Die Quellen eines Laufs. Nur Upload, ein Workspace wird nicht mehr angezapft."""
    from src.services import sources as quellen

    if mode != "files":
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))
    return await quellen.read_uploads(files, locale=locale,
                                      hoechstens=PRAESENTATION_MAX_SOURCES,
                                      schluessel="praesentation")


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

    from src.services import sources as quellen

    durchsuchbar: tuple[int | None, list[str] | None] = (None, None)
    gelesen = await _quellen_lesen(mode, files, locale)
    text = quellen.as_block(gelesen)
    label = quellen.label(gelesen)
    if not text.strip():
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))

    vorlage_bytes, analyse, meta, fallback = vorlagen.aufloesen(user_id, einstellungen.template_id)
    einstellungen.template_name = meta["name"]
    einstellungen.style_text = meta["style_text"]
    einstellungen.template_fallback = fallback
    einstellungen.source_label = label
    # Kept for a slide added later, it searches the same sources on its own.
    einstellungen.workspace_id, einstellungen.source_uuids = durchsuchbar[0], durchsuchbar[1] or []
    if fallback:
        einstellungen.template_id = "thl"

    job_uuid = uuid.uuid4().hex
    db.create_job(job_uuid, user_id, "praesentation", label or "Präsentation", locale=locale)
    quellen.save_sources(user_id, job_uuid, gelesen)
    store.save_params(user_id, job_uuid, einstellungen)
    store.save_template(user_id, job_uuid, vorlage_bytes)
    store.save_template_meta(user_id, job_uuid, analyse)
    task = run_praesentation_outline.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "material"})
    logger.info("Präsentation {} gestartet, {} Zeichen Material",
                job_uuid[:8], len(text))
    return {"job_uuid": job_uuid}
