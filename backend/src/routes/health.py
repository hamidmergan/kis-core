from fastapi import APIRouter

from src import database as db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/maintenance")
async def maintenance_status():
    """Public probe so the frontend can render a maintenance page without auth."""
    enabled = db.get_setting("maintenance_mode", "false").lower() == "true"
    return {"enabled": enabled}


@router.get("/health/labels")
async def ui_labels():
    """Public UI labels (e.g. customizable 'Workspace' wording).

    Read pre-login by the frontend to render the right vocabulary everywhere.
    Returns both locales so the client picks the one matching its UI locale
    without a re-fetch on language switch. Legacy unsuffixed keys fall back
    as DE defaults for back-compat with older deployments.
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
        # Home-page notice banner: shown to all users on the start page above
        # "Nächste Termine". Read here (public) so the home page renders it
        # without admin rights.
        "home_notice_enabled": db.get_setting("home_notice_enabled", "false").lower() == "true",
        "home_notice_text": db.get_setting("home_notice_text", ""),
    }
