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


def _normalized(s: str) -> str:
    return re.sub(r"[\s.]+", "", s).lower()


def _find_matches(text: str, places: list[dict]) -> list[tuple[int, int, dict]]:
    """First mention of each place as (start, end, place), in reading order."""
    if not text or not places:
        return []
    found: list[tuple[int, int, dict]] = []
    for place in places:
        best: tuple[int, int] | None = None
        for name in _names_of(place):
            m = _pattern(name).search(text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m.end())
        if best is not None:
            found.append((best[0], best[1], place))
    found.sort(key=lambda t: t[0])
    return found


def find_places(text: str, places: list[dict], limit: int = CAMPUS_PLACE_CARDS_MAX) -> list[dict]:
    """Places in order of first mention, at most ``limit`` of them."""
    cards = []
    for _, _, place in _find_matches(text, places)[:limit]:
        title = place.get("title") or {}
        cards.append({
            "id": place["id"],
            "code": place.get("code"),
            "title": title if isinstance(title, dict) else {"de": str(title), "en": str(title)},
            "show": show_param(place),
        })
    return cards


def annotate_buildings(
    text: str, places: list[dict], answer_language: str | None = None, limit: int = CAMPUS_PLACE_CARDS_MAX,
) -> str:
    """Adds "(Gebäude A.1)" after a place's first mention, unless the model already named the code there.

    The map chip for a place is only self-explanatory once the reader knows why it showed up; the model
    often names an office ("Zulassungsstelle") without the building code behind it, since the retrieved
    documents for the question rarely include the place's own page.
    """
    matches = [m for m in _find_matches(text, places)[:limit] if m[2].get("code")]
    word = "Gebäude" if (answer_language or "").strip().lower().startswith("german") else "Building"
    for start, end, place in sorted(matches, key=lambda t: t[0], reverse=True):
        code = place["code"]
        mentioned = text[start:end]
        tail = text[end:end + len(code) + 8]
        if _normalized(mentioned) == _normalized(code) or _normalized(code) in _normalized(tail):
            continue
        text = f"{text[:end]} ({word} {code}){text[end:]}"
    return text
