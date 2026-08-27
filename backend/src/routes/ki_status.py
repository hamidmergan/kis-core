"""Says publicly whether a feature is configured, without revealing names."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.dependencies import get_current_user
from src.features.ai_providers.repository.feature_routes import FEATURES
from src.services.feature_router import is_configured

router = APIRouter(prefix="/ki", tags=["ki"])


@router.get("/feature-status")
async def feature_status(
    features: str = Query(default="", description="Comma-separated feature ids; empty = all"),
    _user: dict = Depends(get_current_user),
):
    """Returns a yes or no per feature, for logged-in users only."""
    requested = [f.strip() for f in features.split(",") if f.strip()] or list(FEATURES)
    valid = [f for f in requested if f in FEATURES]
    return {"status": {f: is_configured(f) for f in valid}}
