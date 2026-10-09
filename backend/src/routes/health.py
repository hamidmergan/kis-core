from fastapi import APIRouter

from src import database as db

router = APIRouter(tags=["health"])

# Shipped default for the first-login welcome dialog, editable in Admin -> System.
DEFAULT_WELCOME_MODAL_TEXT = (
    "KIS ist ein Pilotprojekt an der TH Lübeck, eine KI-Plattform für Lehre und "
    "Studium.\n\nWir sind noch in einer frühen Testphase. Die Rechenkapazität für "
    "die KI ist aktuell begrenzt, bei vielen gleichzeitigen Anfragen kann eine "
    "Antwort etwas auf sich warten lassen. Bitte hab in solchen Momenten etwas Geduld."
)


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
    """Public labels, both languages at once."""
    return {
        # The notice banner is read publicly so the start page can show it without rights.
        "home_notice_enabled": db.get_setting("home_notice_enabled", "false").lower() == "true",
        "home_notice_text": db.get_setting("home_notice_text", ""),
        # First-login welcome dialog, read publicly so it can show right after sign-in.
        "welcome_modal_enabled": db.get_setting("welcome_modal_enabled", "true").lower() == "true",
        "welcome_modal_text": db.get_setting("welcome_modal_text", DEFAULT_WELCOME_MODAL_TEXT),
    }
