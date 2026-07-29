"""Public feature-status endpoint.

Tool pages query this to find out whether the AI features they depend on are
configured. The response is intentionally boolean-only - no provider names or
URLs leak to non-admin users.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.dependencies import get_current_user
from src.features.ai_providers.repository.feature_routes import FEATURES
from src.services.feature_router import is_configured

router = APIRouter(prefix="/ki", tags=["ki"])


@router.get("/feature-status")
def feature_status(
    features: str = Query(default="", description="Comma-separated feature ids; empty = all"),
    _user: dict = Depends(get_current_user),
):
    """Return ``{ feature: configured }`` for the requested feature ids.

    Authenticated only (a logged-in tool user) - no admin requirement, and no
    information that wouldn't already be inferable from successful tool use.
    """
    requested = [f.strip() for f in features.split(",") if f.strip()] or list(FEATURES)
    valid = [f for f in requested if f in FEATURES]
    return {"status": {f: is_configured(f) for f in valid}}
