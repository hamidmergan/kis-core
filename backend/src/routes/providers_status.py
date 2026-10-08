"""Shows every logged-in user which named provider currently answers, for the three functions users pick between."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies import get_current_user
from src.services import provider_check

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/status")
def providers_status(_user: dict = Depends(get_current_user)):
    """Result of the last real call per provider and function, checked again first when it is too old."""
    provider_check.run_checks(force=False)
    return provider_check.status()


@router.post("/status/refresh")
def providers_status_refresh(_user: dict = Depends(get_current_user)):
    """Checks every provider again with a real call, at most once a minute however often it is pressed."""
    provider_check.run_checks(force=True)
    return provider_check.status()
