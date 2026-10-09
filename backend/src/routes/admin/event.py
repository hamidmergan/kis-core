"""The stands and the event block of the start page, edited by whoever holds the event right."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.dependencies_rbac import require_full_admin, require_permission
from src.features.event import repository as repo
from src.features.event.service import EventValidationError, normalize_code, validate_config
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_EVENT
from src.routes.event import _card, _now_ms, _visitor

router = APIRouter(prefix="/event", tags=["admin: event"])

_require = require_permission(PERM_SET_EVENT)


class Text2Payload(BaseModel):
    de: str = ""
    en: str = ""


class StationPayload(BaseModel):
    id: str
    code: str
    icon: str
    name: Text2Payload
    blurb: Text2Payload
    francis: Text2Payload


class EventTilePayload(BaseModel):
    id: str
    icon: str
    title: Text2Payload
    body: Text2Payload
    button: Text2Payload
    # The target is a tagged union, the service checks its kind.
    target: dict[str, Any]
    active: bool = False
    availableFrom: str = ""


class EventBlockPayload(BaseModel):
    enabled: bool = False
    ignoreWindow: bool = False
    # ``from`` is a Python keyword, the wire keeps the name of the contract.
    from_: str = Field("", alias="from")
    until: str = ""
    heading: Text2Payload
    text: Text2Payload
    tiles: list[EventTilePayload] = []


class EventConfigPayload(BaseModel):
    stations: list[StationPayload]
    eventBlock: EventBlockPayload
    # Posters then carry the QR code only, the codes are told at the stand.
    hideCodeOnPosters: bool = False


@router.get("")
def get_event(admin: dict = Depends(_require)):
    return repo.get_config()


@router.put("")
def save_event(
    payload: EventConfigPayload,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    try:
        config = validate_config(payload.model_dump(by_alias=True))
    except EventValidationError as fehler:
        raise HTTPException(status_code=422, detail=t(fehler.key, locale, **fehler.params))
    repo.save_config(config)
    return config


@router.get("/stats")
def event_stats(admin: dict = Depends(_require)):
    ids = [stand["id"] for stand in repo.get_config()["stations"]]
    besuche = repo.visits_by_station()
    return {
        "visitsByStation": {stand_id: besuche.get(stand_id, 0) for stand_id in ids},
        "completeCards": repo.complete_cards(ids),
    }


@router.delete("/card")
def reset_own_card(admin: dict = Depends(_require), besucher: str = Depends(_visitor)):
    """Empties the card of this browser so the holder of the right can walk the stands again."""
    repo.delete_stamps_for(besucher)
    repo.clear_failures(besucher)
    return _card(besucher, repo.get_config()["stations"], _now_ms())


@router.delete("/card/{code}")
def reset_one_card(code: str, admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    """Empties the card behind a visitor's own code, told to staff at a stand."""
    besucher = repo.visitor_hash_for_code(normalize_code(code))
    if besucher is None:
        raise HTTPException(status_code=404, detail=t("event.visitorCodeNotFound", locale))
    repo.delete_stamps_for(besucher)
    repo.clear_failures(besucher)
    return {"ok": True}


@router.delete("/stamps")
def reset_all_stamps(admin: dict = Depends(require_full_admin)):
    repo.delete_all_stamps()
    repo.delete_all_visitor_codes()
    return {"ok": True}
