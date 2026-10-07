"""Finds places of the campus map that an answer talks about, by their codes and names."""
import re

from src.limits import CAMPUS_PLACE_CARDS_MAX


def _names_of(place: dict) -> list[str]:
    names: list[str] = []
    if place.get("code"):
        names.append(place["code"])
    for field in ("title", "name"):
        value = place.get(field) or {}
        if isinstance(value, dict):
            names.extend(v for v in value.values() if v)
    for fac in place.get("facilities") or []:
        if isinstance(fac, dict):
            names.extend(v for v in fac.values() if v)
    return [n.strip() for n in names if n and len(n.strip()) >= 3]


_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _roman(n: int) -> str:
    out = ""
    for value, letters in _ROMAN:
        while n >= value:
            out += letters
            n -= value
    return out


def _part_pattern(part: str, previous: str | None) -> str:
    # A number after a word of two or more letters may also be a Roman numeral, as in MFC VII.
    if part.isdigit() and 0 < int(part) < 4000 and previous and len(previous) >= 2 and previous.isalpha():
        return rf"(?:{re.escape(part)}|(?-i:{_roman(int(part))}))"
    return re.escape(part)


def _pattern(name: str) -> re.Pattern:
    # Codes like B.59 or MFC 7 may be written with or without their separator.
    raw = [p for p in re.split(r"[\s.]+", name) if p]
    parts = [_part_pattern(p, raw[i - 1] if i else None) for i, p in enumerate(raw)]
    body = r"[\s.]?".join(parts) if len(parts) > 1 else re.escape(name)
    return re.compile(rf"(?<![\w.]){body}(?![\w])", re.IGNORECASE)


def show_param(place: dict) -> str:
    """What the map's show parameter expects: the code without spaces, else the id."""
    code = (place.get("code") or "").replace(" ", "")
    return code or place["id"]


def find_places(text: str, places: list[dict], limit: int = CAMPUS_PLACE_CARDS_MAX) -> list[dict]:
    """Places in order of first mention, at most ``limit`` of them."""
    if not text or not places:
        return []
    found: list[tuple[int, dict]] = []
    for place in places:
        best: int | None = None
        for name in _names_of(place):
            m = _pattern(name).search(text)
            if m and (best is None or m.start() < best):
                best = m.start()
        if best is not None:
            found.append((best, place))
    found.sort(key=lambda t: t[0])
    cards = []
    for _, place in found[:limit]:
        title = place.get("title") or {}
        cards.append({
            "id": place["id"],
            "code": place.get("code"),
            "title": title if isinstance(title, dict) else {"de": str(title), "en": str(title)},
            "show": show_param(place),
        })
    return cards
