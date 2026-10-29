"""The stand page and the stamp card of a visitor, no account needed."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.features.event import repository as repo
from src.features.event.service import (
    build_card,
    is_valid_email,
    is_valid_visitor_id,
    normalize_email,
    public_view,
    station_by_code,
    visitor_hash,
)
from src.i18n import get_locale, t

router = APIRouter(prefix="/event", tags=["event"])

# The window of the event block is a calendar day where the event takes place.
_TZ_BERLIN = ZoneInfo("Europe/Berlin")


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _visitor(
    x_visitor_id: str | None = Header(default=None),
    locale: str = Depends(get_locale),
) -> str:
    """The hash of the browser's id, only that hash ever reaches storage."""
    if not is_valid_visitor_id(x_visitor_id):
        raise HTTPException(status_code=400, detail=t("event.invalidVisitorId", locale))
    return visitor_hash(x_visitor_id)


def _card(besucher: str, stations: list[dict], jetzt: int) -> dict:
    gesperrt_bis, versuche = repo.lock_state(besucher, jetzt)
    karte = build_card(
        stamped=repo.stamps_for(besucher),
        station_ids=[stand["id"] for stand in stations],
        locked_until=gesperrt_bis,
        attempts_left=versuche,
    )
    karte["code"] = repo.peek_visitor_code(besucher)
    karte["raffleEmail"] = repo.raffle_email_for(besucher)
    return karte


@router.get("/public")
def public_config():
    heute = datetime.now(_TZ_BERLIN).date()
    return public_view(repo.get_config(), heute)


@router.get("/card")
def read_card(besucher: str = Depends(_visitor)):
    return _card(besucher, repo.get_config()["stations"], _now_ms())


class StampPayload(BaseModel):
    stationId: str = Field(..., min_length=1, max_length=64)


@router.post("/stamp")
def stamp_by_station(
    payload: StampPayload,
    besucher: str = Depends(_visitor),
    locale: str = Depends(get_locale),
):
    stations = repo.get_config()["stations"]
    if not any(stand["id"] == payload.stationId for stand in stations):
        raise HTTPException(status_code=404, detail=t("event.stationNotFound", locale))
    repo.add_stamp(besucher, payload.stationId)
    # The visitor's own code is made on the first real stamp, not on a bare page view.
    repo.visitor_code(besucher)
    return {"card": _card(besucher, stations, _now_ms()), "stationId": payload.stationId}


class CodePayload(BaseModel):
    code: str = Field(..., max_length=32)


@router.post("/code")
def stamp_by_code(payload: CodePayload, besucher: str = Depends(_visitor)):
    stations = repo.get_config()["stations"]
    jetzt = _now_ms()
    gesperrt_bis, versuche = repo.lock_state(besucher, jetzt)
    stand_id = None
    if gesperrt_bis is not None:
        # A locked visitor gets no comparison, so the lock cannot be probed.
        ergebnis = "locked"
    else:
        stand = station_by_code(stations, payload.code)
        if stand is not None:
            repo.add_stamp(besucher, stand["id"])
            repo.visitor_code(besucher)
            ergebnis, stand_id = "stamped", stand["id"]
        else:
            gesperrt_bis, versuche = repo.register_failure(besucher, jetzt)
            ergebnis = "wrong"
    karte = build_card(
        stamped=repo.stamps_for(besucher),
        station_ids=[stand["id"] for stand in stations],
        locked_until=gesperrt_bis,
        attempts_left=versuche,
    )
    karte["code"] = repo.peek_visitor_code(besucher)
    karte["raffleEmail"] = repo.raffle_email_for(besucher)
    return {"result": ergebnis, "stationId": stand_id, "card": karte}


class RafflePayload(BaseModel):
    email: str = Field(..., max_length=320)


@router.put("/raffle")
def enter_raffle(payload: RafflePayload, besucher: str = Depends(_visitor), locale: str = Depends(get_locale)):
    """Puts a full card into the raffle, the address replaces an earlier one of this card."""
    config = repo.get_config()
    if not config["raffle"]["enabled"]:
        raise HTTPException(status_code=404, detail=t("event.raffleOff", locale))
    karte = _card(besucher, config["stations"], _now_ms())
    if karte["completedAt"] is None:
        raise HTTPException(status_code=409, detail=t("event.raffleCardIncomplete", locale))
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=422, detail=t("event.raffleEmailInvalid", locale))
    repo.save_raffle_entry(besucher, email)
    karte["raffleEmail"] = email
    return karte


@router.post("/raffle/withdraw")
def withdraw_from_raffle(payload: RafflePayload, besucher: str = Depends(_visitor), locale: str = Depends(get_locale)):
    """Takes an address out of the raffle, the answer never tells whether it was in."""
    if not repo.withdraw_allowed(besucher):
        raise HTTPException(status_code=429, detail=t("event.raffleTooMany", locale))
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=422, detail=t("event.raffleEmailInvalid", locale))
    repo.delete_raffle_entry_by_email(email)
    return {"ok": True}
