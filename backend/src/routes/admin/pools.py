"""Die Vorraete plattformweit leeren: Aufgaben je Werkzeug und Zeitplan-Auswertungen.

Beide Vorraete wachsen als Nebenprodukt der Nutzung und liegen an der Quelle, nicht am
Kursraum. Wer sie loswerden will, musste sie bisher Quelle fuer Quelle neu hochladen.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies_rbac import require_permission
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_AIA_SOURCES

router = APIRouter(tags=["admin: pools"])

# Die Karte steht bei den Quellen, weil beide Vorraete an der Quelle haengen.
_require = require_permission(PERM_SET_AIA_SOURCES)


class ClearPoolsRequest(BaseModel):
    tools: list[str] = []
    schedule: bool = False


@router.get("/pools")
async def get_pools(_admin=Depends(_require)):
    """Was gerade in den Vorraeten liegt. Wer etwas wegwirft, soll es vorher sehen."""
    return {
        "tools": db.pool_counts_by_tool(),
        "schedule": db.count_source_extractions(),
    }


@router.post("/pools/clear")
async def clear_pools(
    body: ClearPoolsRequest, admin=Depends(_require), locale: str = Depends(get_locale)
):
    """Die gewaehlten Vorraete leeren.

    Ohne Auswahl passiert nichts und die Anfrage ist ein Fehler: ein Fehlklick auf einen
    Knopf, der dann alles raeumt, waere die schlimmste Auslegung.
    """
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
