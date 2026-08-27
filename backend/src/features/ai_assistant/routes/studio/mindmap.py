"""KI-Assistent routes - mindmap."""


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

@router.post("/ai-assistant/workspaces/{workspace_uuid}/mindmap/generate")
async def generate_mindmap(
    workspace_uuid: str,
    body: schemas.MindmapGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue mindmap generation as a background Celery task."""
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

    # Build uuid→id mapping for the task
    source_uuids = []
    for suuid in body.active_source_ids:
        s = db.get_aia_source(suuid)
        if s and s["id"] in source_ids:
            source_uuids.append(suuid)

    # Create DB record
    mindmap_id = db.create_aia_mindmap(workspace["id"], user_id, source_ids)

    # Queue: through the shared-pool dispatcher when enabled, else direct .delay.
    from src.features.ai_assistant.scheduling.service import scheduler_enabled, enqueue_task
    if scheduler_enabled():
        enqueue_task(
            "aia.generate_mindmap", user_id,
            args=[mindmap_id, source_ids, source_uuids],
            kwargs={"locale": locale, "user_id": user_id},
        )
    else:
        from src.tasks.aia_tasks import run_generate_mindmap
        run_generate_mindmap.delay(mindmap_id, source_ids, source_uuids, locale=locale, user_id=user_id)

    return {"mindmap_id": mindmap_id, "status": "pending"}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmap/{mindmap_id}")
async def get_mindmap(
    workspace_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Poll mindmap generation status."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    mindmap = db.get_aia_mindmap(mindmap_id)
    if not mindmap or mindmap["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("mindmap.notFound", locale))

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmap")
async def get_latest_mindmap(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Get the latest mindmap for this workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    mindmap = db.get_latest_aia_mindmap(workspace["id"], user_id)
    if not mindmap:
        return {"id": None, "status": None, "mindmap": None, "error": None}

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmaps")
async def list_mindmaps(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """List all saved mindmaps for this workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    rows = db.get_all_aia_mindmaps(workspace["id"], user_id)
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
            # The display name comes ready from the query, own title before root node.
            "topic": r["topic"] or "Mindmap",
        }
        for r in rows
    ]

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/mindmap/{mindmap_id}")
async def delete_mindmap(
    workspace_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Delete a mindmap."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    mindmap = db.get_aia_mindmap(mindmap_id)
    if not mindmap or mindmap["workspace_id"] != workspace["id"] or mindmap["user_id"] != user_id:
        raise HTTPException(status_code=404, detail=t("mindmap.notFound", locale))

    db.delete_aia_mindmap(mindmap_id)
    return {"ok": True}

@router.patch("/ai-assistant/workspaces/{workspace_uuid}/mindmap/{mindmap_id}/title")
async def rename_mindmap(
    workspace_uuid: str,
    mindmap_id: int,
    body: schemas.ArtifactTitleBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Change the name of a mind map, without one the list shows the root node."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    titel = db.clean_title(body.title)
    if not titel:
        raise HTTPException(status_code=400, detail=t("title.empty", locale))

    # Someone else's row: 404 instead of 403, as on the delete route above.
    if not db.update_artifact_title("mindmap", mindmap_id, user_id, workspace["id"], titel):
        raise HTTPException(status_code=404, detail=t("mindmap.notFound", locale))
    return {"ok": True, "title": titel}

