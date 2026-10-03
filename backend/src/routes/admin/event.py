"""The stands and the event block of the start page, edited by whoever holds the event right."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.dependencies_rbac import require_permission
from src.features.event import repository as repo
from src.features.event.service import EventValidationError, validate_config
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_EVENT

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
