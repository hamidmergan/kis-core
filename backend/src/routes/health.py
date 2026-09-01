from fastapi import APIRouter

from src import database as db

router = APIRouter(tags=["health"])

# Shipped default for the first-login welcome dialog, editable in Admin -> System.
DEFAULT_WELCOME_MODAL_TEXT = (
    "KIS ist die KI-Plattform der TH Lübeck für Lehre und Studium. Sie bietet "
    "eigenständige Werkzeuge, etwa Übersetzung, Screencast und Zusammenfassung, sowie "
    "Module mit einem KI-Studienassistenten, der Fragen zu den Kursmaterialien "
    "beantwortet.\n\nMehr in der Dokumentation, oben rechts im Zahnrad-Menü."
)


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
        # First-login welcome dialog, read publicly so it can show right after sign-in.
        "welcome_modal_enabled": db.get_setting("welcome_modal_enabled", "true").lower() == "true",
        "welcome_modal_text": db.get_setting("welcome_modal_text", DEFAULT_WELCOME_MODAL_TEXT),
    }
