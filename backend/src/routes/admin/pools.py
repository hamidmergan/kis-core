"""Clears the pools platform wide: exercises per tool and schedule analyses."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies_rbac import require_permission
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_AIA_SOURCES

router = APIRouter(tags=["admin: pools"])

# The card sits with the sources because both pools hang off the source.
_require = require_permission(PERM_SET_AIA_SOURCES)


class ClearPoolsRequest(BaseModel):
    tools: list[str] = []
    schedule: bool = False


@router.get("/pools")
def get_pools(_admin=Depends(_require)):
    """What currently sits in the pools, you should see it before throwing it away."""
    return {
        "tools": db.pool_counts_by_tool(),
        "schedule": db.count_source_extractions(),
    }


@router.post("/pools/clear")
def clear_pools(
    body: ClearPoolsRequest, admin=Depends(_require), locale: str = Depends(get_locale)
):
    """Clears the chosen pools, without a selection the request is an error."""
    unbekannt = [tool for tool in body.tools if tool not in db.POOL_TOOLS]
    if unbekannt or not (body.tools or body.schedule):
        raise HTTPException(status_code=400, detail=t("admin.pools.nothingChosen", locale))
    items = db.clear_pool_for_tools(body.tools) if body.tools else 0
    extractions = db.clear_source_extractions() if body.schedule else 0
    logger.info(
        "Vorraete geleert von {}: {} Aufgaben ({}), {} Zeitplan-Auswertungen",
        admin.get("email"), items, ", ".join(body.tools) or "keine", extractions,
    )
    return {"items_deleted": items, "extractions_deleted": extractions}
