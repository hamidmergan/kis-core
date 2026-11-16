"""What a source is about, read only when somebody opens it."""
from ._shared import (
    APIRouter, Depends, HTTPException, db, get_current_user, logger,
    get_locale, t, _load_workspace_source, _require_workspace_manage,
)
from src.features.ai_assistant.routes._workspace_access import _require_workspace_member

router = APIRouter(tags=["ki-assistent: sources"])


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/summary")
def get_source_summary(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The stored summary of one source, for everybody who may see the module."""
    workspace = _require_workspace_member(workspace_uuid, current_user["user_id"], locale)
    source = _load_workspace_source(source_uuid, workspace, locale)
    return {"summary": source.get("summary") or ""}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/summary")
def create_source_summary(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Catches up on the summary of a finished source that has none, owner only."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    source = _load_workspace_source(source_uuid, workspace, locale)
    if (source["status"] != "ready" or source.get("progress")
            or (source.get("summary") or "").strip()):
        raise HTTPException(status_code=409, detail=t("ai.source.summaryNotPossible", locale))

    from src.features.ai_assistant.tasks.ingestion import run_summarize_source
    # Set before dispatch so the row spins at once and a second click bounces off.
    db.update_aia_source_progress(source_uuid, "summarizing")
    try:
        run_summarize_source.delay(source_uuid)
    except Exception:
        db.clear_aia_source_progress(source_uuid)
        raise

    logger.info("KI Tutor: summary of source {} dispatched", source_uuid)
    return {"uuid": source_uuid, "progress": {"stage": "summarizing"}}
