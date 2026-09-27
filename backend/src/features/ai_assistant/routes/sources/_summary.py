"""What a source is about, read only when somebody opens it."""
from ._shared import (
    APIRouter, Depends, HTTPException, db, get_current_user,
    get_locale, t, _load_workspace_source,
)

router = APIRouter(tags=["ki-assistent: sources"])


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/summary")
def get_source_summary(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The stored summary of one source, for everybody who may see the module."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    if not is_owner and not db.is_student_enrolled(workspace["id"], user_id):
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = _load_workspace_source(source_uuid, workspace, locale)
    return {"summary": source.get("summary") or ""}
