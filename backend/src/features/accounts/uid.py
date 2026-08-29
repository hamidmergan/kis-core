"""Turns free text into a user name LDAP accepts."""
import re
from collections.abc import Callable

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
_UNERLAUBT = re.compile(r"[^a-z0-9_.-]")
_UID = re.compile(r"^[a-z0-9_.-]{2,32}$")
MAX_UID_LENGTH = 32


def slugify_uid(text: str) -> str | None:
    """Returns a usable user name or None when nothing is left over."""
    wert = (text or "").strip().lower()
    for zeichen, ersatz in _UMLAUTE.items():
        wert = wert.replace(zeichen, ersatz)
    wert = wert.replace(" ", "-")
    wert = _UNERLAUBT.sub("", wert)
    return wert if _UID.match(wert) else None


def name_to_uid(given_name: str, surname: str) -> str | None:
    """Builds vorname.nachname, None when one of the two carries nothing usable."""
    vorname = slugify_uid(given_name)
    nachname = slugify_uid(surname)
    if not vorname or not nachname:
        return None
    return slugify_uid(f"{vorname}.{nachname}"[:MAX_UID_LENGTH])


def unique_uid(base: str, exists: Callable[[str], bool]) -> str:
    """Appends the smallest free number, the result never grows past the limit."""
    if not exists(base):
        return base
    nummer = 2
    while True:
        endung = str(nummer)
        stamm = base[: MAX_UID_LENGTH - len(endung)]
        kandidat = f"{stamm}{endung}"
        if not exists(kandidat):
            return kandidat
        nummer += 1
