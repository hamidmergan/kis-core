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
