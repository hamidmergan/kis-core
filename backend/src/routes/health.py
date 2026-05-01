from fastapi import APIRouter

from src import database as db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/maintenance")
def maintenance_status():
    """Public probe so the frontend can render a maintenance page without auth."""
    enabled = db.get_setting("maintenance_mode", "false").lower() == "true"
    return {"enabled": enabled}


@router.get("/health/labels")
def ui_labels():
    """Public UI labels (e.g. customizable 'Workspace' wording).

    Read pre-login by the frontend to render the right vocabulary everywhere.
    Also exposes the system-wide mascot toggle so unauthenticated pages
    (login, wartung, pending) honour the admin's choice.
    """
    return {
        "workspace_singular": db.get_setting("workspace_label_singular", "Workspace"),
        "workspace_plural": db.get_setting("workspace_label_plural", "Workspaces"),
        "mascot_enabled": db.get_setting("mascot_enabled", "true").lower() == "true",
    }
