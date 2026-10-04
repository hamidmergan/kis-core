"""The campus map link for the footer, open to everyone because the footer is."""
from fastapi import APIRouter

from src.features.campus.services import settings as campus_settings

router = APIRouter(prefix="/campus", tags=["campus: public"])


@router.get("/map")
def campus_map():
    return {"map_url": campus_settings.read().map_url}
