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
    Returns both locales so the client picks the one matching its UI locale
    without a re-fetch on language switch. Legacy unsuffixed keys fall back
    as DE defaults for back-compat with older deployments.
    Also exposes the system-wide mascot toggle so unauthenticated pages
    (login, wartung, pending) honour the admin's choice.
    """
    return {
        "workspace_singular_de": db.get_setting(
            "workspace_label_singular_de",
            db.get_setting("workspace_label_singular", "Workspace"),
        ),
        "workspace_plural_de": db.get_setting(
            "workspace_label_plural_de",
            db.get_setting("workspace_label_plural", "Workspaces"),
        ),
        "workspace_singular_en": db.get_setting("workspace_label_singular_en", "Workspace"),
        "workspace_plural_en": db.get_setting("workspace_label_plural_en", "Workspaces"),
        "mascot_enabled": db.get_setting("mascot_enabled", "true").lower() == "true",
    }
