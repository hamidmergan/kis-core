"""The first step: material and template in, the outline task out."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import ValidationError

from src import database as db
from src.dependencies import get_current_user
from src.features.praesentation import material, store, vorlagen
from src.features.praesentation.schemas import LANGUAGES, PraesentationParams
from src.i18n import get_locale, t
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

    durchsuchbar: tuple[int | None, list[str] | None] = (None, None)
    if mode == "files":
        quellen, label = await material.aus_dateien(files, locale)
    elif mode == "module":
        try:
            uuids = json.loads(source_uuids)
        except json.JSONDecodeError:
            uuids = []
        if not workspace_uuid or not uuids:
            raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))
        quellen, label, modul = material.aus_workspace(workspace_uuid, uuids, user_id, locale)
        if modul:
            durchsuchbar = (modul["id"], uuids)
    else:
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))
    if not quellen:
        raise HTTPException(status_code=422, detail=t("praesentation.noContent", locale))
    # Only laid down here. Reading every source into facts costs one model call each and
    # belongs in the task, a web request must not wait for that.
    roh = material.als_quellen(quellen)
    if not roh:
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
    store.save_material(user_id, job_uuid, roh, durchsuchbar[0], durchsuchbar[1] or [])
    store.save_params(user_id, job_uuid, einstellungen)
    store.save_template(user_id, job_uuid, vorlage_bytes)
    store.save_template_meta(user_id, job_uuid, analyse)
    task = run_praesentation_outline.apply_async(args=[job_uuid, user_id, locale])
    db.set_job_celery_task_id(job_uuid, task.id)
    db.update_job_status(job_uuid, "pending", progress={"step": "material"})
    zeichen = sum(len(q["content"]) for q in roh)
    logger.info("Präsentation {} gestartet, {} Quelle(n), {} Zeichen roh",
                job_uuid[:8], len(roh), zeichen)
    return {"job_uuid": job_uuid}
