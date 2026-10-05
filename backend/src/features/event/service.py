"""Pure rules of the event stamp card, without database and without Redis."""
import hashlib
import hmac
import re
from datetime import date

# No I, O, 0 or 1, so a code read off a poster cannot be mixed up.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4
MAX_TILES = 4
TILE_TARGET_KINDS = ("stamp", "info", "internal", "directLogin")

# The browser makes the id up, anything else is a stray request.
_VISITOR_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The fields a visitor may see of a stand, the code is deliberately missing.
_PUBLIC_STATION_FIELDS = ("id", "icon", "name", "blurb", "francis")


class EventValidationError(ValueError):
    """The configuration breaks a rule, the key names the message and the params fill it."""

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


def _text(de: str, en: str) -> dict:
    return {"de": de, "en": en}


def _station(id: str, code: str, icon: str, de: tuple[str, str, str], en: tuple[str, str, str]) -> dict:
    return {
        "id": id,
        "code": code,
        "icon": icon,
        "name": _text(de[0], en[0]),
        "blurb": _text(de[1], en[1]),
        "francis": _text(de[2], en[2]),
    }


def default_config() -> dict:
    """The stands and the event block a fresh install shows until the admin saves its own."""
    return {
        "hideCodeOnPosters": False,
        "stations": [
            _station(
                "management", "H4RV", "info",
                ("Projekt KIS", "Ziele, Antrag und Zeitplan",
                 "Hier hast du gesehen, wofür das Projekt KIS steht und wie es aufgebaut ist."),
                ("Project KIS", "Goals, proposal and schedule",
                 "Here you saw what the KIS project stands for and how it is organised."),
            ),
            _station(
                "study", "P9KT", "francis",
                ("Studium", "Assistent, Microcredentials und Fachlandkarte",
                 "Hier hast du gesehen, wie das Studium auf internationale Studierende abgestimmt wird."),
                ("Studies", "Assistant, microcredentials and subject map",
                 "Here you saw how the degree programme is adapted for international students."),
            ),
            _station(
                "platform", "M3XD", "platform",
                ("KIS-Plattform", "KI-Fachsprachen-Trainer und Übersetzung",
                 "Hier hast du gesehen, wie die KIS-Plattform Materialien übersetzt und beim Fachwortschatz hilft."),
                ("KIS platform", "AI technical-language trainer and translation",
                 "Here you saw how the KIS platform translates materials and helps with technical vocabulary."),
            ),
            _station(
                "dafl", "W7NC", "translation",
                ("Deutsch als Fremdsprache", "Sprachkurse und Buddy-Programm",
                 "Hier hast du gesehen, wie Deutschkurse und Buddys internationale Studierende begleiten."),
                ("German as a foreign language", "Language courses and buddy programme",
                 "Here you saw how German courses and buddies support international students."),
            ),
            _station(
                "intercultural", "T6QB", "lightbulb",
                ("Interkulturelle Kompetenzen", "Lernfortschritt und Berufseinstieg",
                 "Hier hast du gesehen, wie Lernstand und Berufseinstieg begleitet werden."),
                ("Intercultural skills", "Learning progress and career entry",
                 "Here you saw how learning progress and the move into work are supported."),
            ),
        ],
        "eventBlock": {
            "enabled": True,
            "ignoreWindow": False,
            "from": "2026-11-06",
            "until": "2026-11-13",
            "heading": _text("Tag der Lehre am 13.11.2026", "Day of Teaching on 13 November 2026"),
            "text": _text(
                "KIS wird vorgestellt. Probiere es direkt aus oder sammle Stempel an allen Ständen.",
                "KIS is presented. Try it right away or collect stamps at all stands.",
            ),
            "tiles": [
                {
                    "id": "demo",
                    "icon": "francis",
                    "title": _text("Demozugang", "Demo access"),
                    "body": _text(
                        "Mit einem Klick in KIS und selbst ausprobieren.",
                        "One click into KIS to try it yourself.",
                    ),
                    "button": _text("Ausprobieren", "Try it"),
                    "target": {"kind": "directLogin", "accessCode": "KIS-DEMO-0000"},
                    "active": False,
                    "availableFrom": "2026-11-13",
                },
                {
                    "id": "stamp",
                    "icon": "star",
                    "title": _text("Stempelkarte", "Stamp card"),
                    "body": _text(
                        "Besuche alle Stände, sammle Stempel und hol dir am Ende dein Geschenk ab.",
                        "Visit all stands, collect stamps and pick up your gift at the end.",
                    ),
                    "button": _text("Karte öffnen", "Open card"),
                    "target": {"kind": "stamp"},
                    "active": False,
                    "availableFrom": "2026-11-13",
                },
            ],
        },
    }


# --- visitors -----------------------------------------------------------------

def is_valid_visitor_id(value: str | None) -> bool:
    return bool(value) and _VISITOR_ID.match(value) is not None


def visitor_hash(visitor_id: str) -> str:
    """Only this hash is ever stored, the id itself stays in the browser."""
    return hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()


# --- codes --------------------------------------------------------------------

def normalize_code(text: str) -> str:
    """Spaces and case do not matter when a code is read off a poster."""
    return "".join(text.split()).upper()


def is_valid_code(code: str) -> bool:
    return len(code) == CODE_LENGTH and all(zeichen in CODE_ALPHABET for zeichen in code)


def station_by_code(stations: list[dict], entered: str) -> dict | None:
    """The stand behind a typed code, every stand is compared so timing tells nothing."""
    code = normalize_code(entered)
    treffer = [stand for stand in stations if hmac.compare_digest(normalize_code(stand["code"]), code)]
    return treffer[0] if treffer else None


# --- time window --------------------------------------------------------------

def is_valid_date_or_empty(value: str) -> bool:
    if value == "":
        return True
    if _ISO_DATE.match(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def event_block_visible(block: dict, today: date) -> bool:
    """Whether the block is shown today, an empty bound leaves that side open."""
    if not block.get("enabled"):
        return False
    if block.get("ignoreWindow"):
        return True
    heute = today.isoformat()
    von, bis = block.get("from") or "", block.get("until") or ""
    return (not von or von <= heute) and (not bis or heute <= bis)


def event_window(config: dict, today: date) -> dict | None:
    """The stamp card's own switch and date, None while the event is off, over or has no stamp tile."""
    block = config["eventBlock"]
    if not block.get("enabled"):
        return None
    heute = today.isoformat()
    if not block.get("ignoreWindow") and (block.get("until") or "") and heute > block["until"]:
        return None
    kachel = next((t for t in block.get("tiles", []) if (t.get("target") or {}).get("kind") == "stamp"), None)
    if kachel is None:
        return None
    return {"active": bool(kachel.get("active")), "availableFrom": kachel.get("availableFrom") or ""}


def public_view(config: dict, today: date) -> dict:
    """What a visitor may see: the stands without their codes, the block only inside its window."""
    block = config["eventBlock"]
    return {
        "stations": [
            {feld: stand[feld] for feld in _PUBLIC_STATION_FIELDS} for stand in config["stations"]
        ],
        "eventBlock": block if event_block_visible(block, today) else None,
        "stamp": event_window(config, today),
    }


# --- the card -----------------------------------------------------------------

def completed_at(stamped: dict[str, int], station_ids) -> int | None:
    """The last stamp once every current stand is stamped, stamps of removed stands do not count."""
    ids = list(station_ids)
    if not ids or any(stand_id not in stamped for stand_id in ids):
        return None
    return max(stamped[stand_id] for stand_id in ids)


def build_card(*, stamped: dict[str, int], station_ids, locked_until: int | None, attempts_left: int) -> dict:
    """The card as the browser shows it, trimmed to the stands that exist right now."""
    ids = list(station_ids)
    aktuell = {stand_id: stamped[stand_id] for stand_id in ids if stand_id in stamped}
    return {
        "stamped": aktuell,
        "completedAt": completed_at(aktuell, ids),
        "lockedUntil": locked_until,
        "attemptsLeft": attempts_left,
    }


# --- the admin form -----------------------------------------------------------

def validate_config(config: dict) -> dict:
    """Checks the rules of the admin form and returns the config with trimmed ids and normalised codes."""
    stations = []
    ids: set[str] = set()
    codes: set[str] = set()
    for stand in config.get("stations", []):
        stand_id = str(stand.get("id", "")).strip()
        if not stand_id:
            raise EventValidationError("event.config.stationIdEmpty")
        if stand_id in ids:
            raise EventValidationError("event.config.stationIdDuplicate", id=stand_id)
        ids.add(stand_id)
        code = normalize_code(str(stand.get("code", "")))
        if not is_valid_code(code):
            raise EventValidationError(
                "event.config.codeInvalid", id=stand_id, length=CODE_LENGTH, alphabet=CODE_ALPHABET
            )
        if code in codes:
            raise EventValidationError("event.config.codeDuplicate", code=code)
        codes.add(code)
        stations.append({**stand, "id": stand_id, "code": code})

    block = dict(config.get("eventBlock") or {})
    for feld in ("from", "until"):
        wert = block.get(feld) or ""
        if not is_valid_date_or_empty(wert):
            raise EventValidationError("event.config.dateInvalid", value=wert)
        block[feld] = wert

    tiles = list(block.get("tiles") or [])
    if len(tiles) > MAX_TILES:
        raise EventValidationError("event.config.tooManyTiles", max=MAX_TILES)
    tile_ids: set[str] = set()
    geprueft = []
    for tile in tiles:
        tile_id = str(tile.get("id", "")).strip()
        if not tile_id:
            raise EventValidationError("event.config.tileIdEmpty")
        if tile_id in tile_ids:
            raise EventValidationError("event.config.tileIdDuplicate", id=tile_id)
        tile_ids.add(tile_id)
        ziel = tile.get("target") or {}
        if ziel.get("kind") not in TILE_TARGET_KINDS:
            raise EventValidationError("event.config.targetKindInvalid", id=tile_id)
        ab = tile.get("availableFrom") or ""
        if not is_valid_date_or_empty(ab):
            raise EventValidationError("event.config.dateInvalid", value=ab)
        geprueft.append({**tile, "id": tile_id, "availableFrom": ab})
    block["tiles"] = geprueft

    return {"stations": stations, "eventBlock": block, "hideCodeOnPosters": bool(config.get("hideCodeOnPosters"))}
