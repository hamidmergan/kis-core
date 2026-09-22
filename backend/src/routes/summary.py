"""Summary route: several sources are condensed into one text along a build plan."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.dependencies_rbac import require_tool_access
from src.features.summary.templates import TEMPLATES, default_template, get_template
from src.i18n import get_locale, t
from src.features.summary import settings as cfg
from src.services import sources
from src.limits import SUMMARY_MAX_SOURCES
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services import feature_provider_choices
from src.services.open_jobs import enforce_open_jobs
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import SUMMARY_EXTENSIONS

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
        "maxCharsPerSource": cfg.chars_per_source(),
        "maxTotalChars": cfg.total_chars(),
        "extensions": sorted(SUMMARY_EXTENSIONS),
    }


@router.post("/summary")
async def summarize(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    mode: str = Form("files"),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    template: str | None = Form(None),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Takes the uploaded sources, files them and starts the condensation."""
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

    # These two are burst guards and must fire before any work is done.
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "summary", locale)

    # Beide Wege enden im selben Datensatz, aus dem Workspace kommt nur die Datei.
    if mode == "module":
        from src.services import workspace_sources as arbeitsraum
        gelesen = arbeitsraum.read_workspace(
            workspace_uuid, arbeitsraum.parse_uuids(source_uuids), user_id=user_id,
            locale=locale, hoechstens=SUMMARY_MAX_SOURCES, schluessel="summary")
    else:
        gelesen = await sources.read_uploads(files, locale=locale,
                                             hoechstens=SUMMARY_MAX_SOURCES,
                                             schluessel="summary")
    namen = [q.dateiname for q in gelesen]

    # Quota is charged only once every source has cleared reading, so a refused start costs nothing.
    enforce_quota(user_id, "summary", is_admin_user(current_user), locale)
    sources.save_sources(user_id, job_uuid, gelesen)

    # The job is created only once every source is safely stored, so a storage failure leaves nothing behind.
    anzeige = namen[0] if len(namen) == 1 else t(
        "summary.jobLabel", locale, name=namen[0], more=len(namen) - 1)
    db.create_job(job_uuid, user_id, "summary", anzeige, locale=locale)

    from src.tasks.summary_tasks import run_summary
    run_summary.delay(job_uuid, vorlage.slug, provider_id)
    logger.info("Zusammenfassung {} eingereiht: {} Quelle(n), {} Zeichen, Vorlage '{}'",
                job_uuid[:8], len(gelesen), sum(len(q.text) for q in gelesen), vorlage.slug)
    return {"job_uuid": job_uuid, "status": "pending"}
