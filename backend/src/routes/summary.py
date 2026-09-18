"""Summary route: several sources are condensed into one text along a build plan."""

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.dependencies_rbac import require_tool_access
from src.features.summary.templates import TEMPLATES, default_template, get_template
from src.i18n import get_locale, t
from src.limits import SUMMARY_MAX_CHARS_PER_SOURCE, SUMMARY_MAX_SOURCES, SUMMARY_MAX_TOTAL_CHARS
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services import feature_provider_choices
from src.services.open_jobs import enforce_open_jobs
from src.services.tool_limits import max_upload_bytes
from src.storage import save_job_file_from_path
from src.utils.file_validation import SUMMARY_EXTENSIONS, validate_or_raise
from src.utils.upload_stream import stream_upload_to_path

router = APIRouter(tags=["summary"], dependencies=[Depends(require_tool_access("summary"))])


@router.get("/summary/providers")
async def list_summary_providers(_user: dict = Depends(get_current_user)):
    """Reachable chat providers, the tool runs on the chat model."""
    return await feature_provider_choices.list_reachable_choices("chat")


@router.get("/summary/templates")
async def list_templates(_user: dict = Depends(get_current_user)):
    """The build plans a person may pick, plus what the tool currently accepts."""
    return {
        "templates": [
            {"slug": v.slug, "nameDe": v.name_de, "nameEn": v.name_en,
             "hintDe": v.hint_de, "hintEn": v.hint_en}
            for v in TEMPLATES
        ],
        "maxSources": SUMMARY_MAX_SOURCES,
        "maxCharsPerSource": SUMMARY_MAX_CHARS_PER_SOURCE,
        "maxTotalChars": SUMMARY_MAX_TOTAL_CHARS,
        "extensions": sorted(SUMMARY_EXTENSIONS),
    }


@router.post("/summary")
async def summarize(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    template: str | None = Form(None),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Takes the uploaded sources, files them and starts the condensation."""
    if not files:
        raise HTTPException(status_code=400, detail=t("summary.noFiles", locale))
    if len(files) > SUMMARY_MAX_SOURCES:
        raise HTTPException(status_code=400,
                            detail=t("summary.tooManySources", locale, max=SUMMARY_MAX_SOURCES))
    if provider_id is not None and not feature_provider_choices.is_eligible("chat", provider_id):
        raise HTTPException(status_code=400, detail=t("summary.invalidProvider", locale))
    vorlage = get_template(template) if template else default_template()
    if vorlage is None:
        raise HTTPException(status_code=400, detail=t("summary.templateMissing", locale))

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t(
            "file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

    user_id = current_user.get("user_id", 0)
    job_uuid = uuid.uuid4().hex
    quellen: list[dict] = []
    namen: list[str] = []

    # Checked first, charged second: a refused start costs no quota.
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "summary", locale)
    enforce_quota(user_id, "summary", is_admin_user(current_user), locale)

    with tempfile.TemporaryDirectory(prefix="summary_upload_") as tmpdir:
        for i, datei in enumerate(files):
            name = datei.filename or ""
            if not name:
                raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
            ext = Path(name).suffix.lower()
            if ext not in SUMMARY_EXTENSIONS:
                raise HTTPException(status_code=400, detail=t(
                    "summary.unsupportedFormat", locale, formats=", ".join(sorted(SUMMARY_EXTENSIONS))))
            ziel = os.path.join(tmpdir, f"input_{i}{ext}")
            groesse, kopf = await stream_upload_to_path(datei, ziel, max_upload_bytes(), locale)
            if not groesse:
                raise HTTPException(status_code=400, detail=t("file.empty", locale))
            validate_or_raise(kopf, ext, locale)
            namen.append(name)
            quellen.append({"filename": name, "local": ziel, "ext": ext})

        anzeige = namen[0] if len(namen) == 1 else t(
            "summary.jobLabel", locale, name=namen[0], more=len(namen) - 1)
        db.create_job(job_uuid, user_id, "summary", anzeige, locale=locale)
        # Numbered, otherwise a second file of the same type overwrites the first.
        for i, quelle in enumerate(quellen):
            quelle["input_path"] = save_job_file_from_path(
                user_id, job_uuid, f"input_{i}{quelle['ext']}", quelle["local"])

    db.set_job_input_path(job_uuid, quellen[0]["input_path"])

    from src.tasks.summary_tasks import run_summary
    run_summary.delay(
        job_uuid,
        [{"filename": q["filename"], "input_path": q["input_path"]} for q in quellen],
        vorlage.slug,
        provider_id,
    )
    logger.info("Zusammenfassung {} eingereiht: {} Quelle(n), Vorlage '{}'",
                job_uuid[:8], len(quellen), vorlage.slug)
    return {"job_uuid": job_uuid, "status": "pending"}
