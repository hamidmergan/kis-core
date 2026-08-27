"""AI assistant routes - data_table."""


from fastapi import APIRouter, Depends, HTTPException


from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst

from src.features.ai_assistant.routes._helpers import (
    _resolve_source_ids,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])

@router.post("/ai-assistant/workspaces/{workspace_uuid}/data_table/generate")
async def generate_data_table(
    workspace_uuid: str,
    body: schemas.DataTableGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    source_ids = _resolve_source_ids(workspace, body.active_source_ids, max_count=5, locale=locale)

    # Build source map for citations
    source_map: dict[int, dict] = {}
    for idx, suuid in enumerate(body.active_source_ids):
        src = db.get_aia_source(suuid)
        if src and src["id"] in source_ids:
            source_map[src["id"]] = {"number": idx + 1, "filename": src["filename"], "uuid": suuid}

    data_table_id = db.create_aia_data_table(workspace["id"], user_id, source_ids)

    from src.tasks.aia_tasks import run_generate_data_table
    # Convert int keys to str for JSON serialization
    source_map_str = {str(k): v for k, v in source_map.items()}
    run_generate_data_table.delay(data_table_id, source_ids, body.active_source_ids, source_map_str,
                                  locale=locale, user_id=user_id)
    return {"data_table_id": data_table_id, "status": "pending"}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/data_table/{data_table_id}")
async def get_data_table(
    workspace_uuid: str,
    data_table_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Poll data_table status."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    dt = db.get_aia_data_table(data_table_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail=t("ai.dataTable.notFound", locale))

    return dt

@router.get("/ai-assistant/workspaces/{workspace_uuid}/data_table")
async def get_latest_data_table(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Get the most recent data_table for a workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    dt = db.get_latest_aia_data_table(workspace["id"], user_id)
    return dt or {}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/data_tables")
async def get_data_tables(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Get all data_tables for a workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    rows = db.get_aia_data_tables_by_workspace(workspace["id"], user_id)
    return [
        {
            "id": r["id"],
            "title": r["title"] or "DataTable",
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
        }
        for r in rows
    ]

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/data_table/{data_table_id}")
async def delete_data_table(
    workspace_uuid: str,
    data_table_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    dt = db.get_aia_data_table(data_table_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail=t("ai.dataTable.notFound", locale))
    db.delete_aia_data_table(data_table_id)
    return {"ok": True}


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/data_table/{data_table_id}/title")
async def rename_data_table(
    workspace_uuid: str,
    data_table_id: int,
    body: schemas.ArtifactTitleBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Change the name of a data table."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    titel = db.clean_title(body.title)
    if not titel:
        raise HTTPException(status_code=400, detail=t("title.empty", locale))

    # Someone else's row: 404 instead of 403, as on the delete route above.
    if not db.update_artifact_title("data_table", data_table_id, user_id, workspace["id"], titel):
        raise HTTPException(status_code=404, detail=t("ai.dataTable.notFound", locale))
    return {"ok": True, "title": titel}


# ─── LanguageTraining: generate exercises (via Celery) ────────────────────────

