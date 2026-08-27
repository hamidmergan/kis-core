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
    """Public labels, both languages at once."""
    return {
        "workspace_singular_de": db.get_setting(
            "workspace_label_singular_de",
            db.get_setting("workspace_label_singular", "Modul"),
        ),
        "workspace_plural_de": db.get_setting(
            "workspace_label_plural_de",
            db.get_setting("workspace_label_plural", "Module"),
        ),
        "workspace_singular_en": db.get_setting("workspace_label_singular_en", "Module"),
        "workspace_plural_en": db.get_setting("workspace_label_plural_en", "Modules"),
        # The notice banner is read publicly so the start page can show it without rights.
        "home_notice_enabled": db.get_setting("home_notice_enabled", "false").lower() == "true",
        "home_notice_text": db.get_setting("home_notice_text", ""),
    }
