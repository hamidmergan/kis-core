"""The outline call: prompt, parsing, and the rules that keep a deck varied."""

from __future__ import annotations

import json
import re

from src.features.praesentation.schemas import (
    FOLIEN_GRENZEN, WAEHLBARE_ROLLEN, Outline, OutlineRow, PraesentationParams,
)

_ROLLE_TEXT = {
    "abschnitt": "a section divider with only a heading",
    "text": "a heading with bullet points",
    "zwei_spalten": "a heading with two columns, each with its own subheading",
    "text_mit_bild": "a heading, bullet points and an illustration",
    "bild_gross": "a heading and one large illustration, no text",
}
SPRACHE = {"de": "German", "en": "English"}
_ID = re.compile(r"^s\d+$")


class Unusable(RuntimeError):
    """The answer was not a usable outline, the caller may try once more."""


def build_messages(source: str, params: PraesentationParams, rollen: list[str],
                   mit_nummern: bool = False) -> list[dict]:
    """The outline call. With a fact pool every entry also names the facts it rests on.

    Without one the material arrives as plain text, and the call stays what it was.
    """
    lo, hi = FOLIEN_GRENZEN
    rollen_text = "\n".join(f"- {r}: {_ROLLE_TEXT[r]}" for r in rollen if r in _ROLLE_TEXT)
    nummern = (
        'Every entry also carries "fact_ids", the numbers of the facts that slide is built '
        "from, taken from the list below. Pick only facts that really belong on that slide, "
        "usually three to eight, and never put the same fact on two slides. A slide that "
        "draws on everything, such as an agenda, carries an empty list.\n"
    ) if mit_nummern else ""
    eintrag = ('{"role": "...", "title": "...", "gist": "...", "fact_ids": [1, 2]}'
               if mit_nummern else '{"role": "...", "title": "...", "gist": "..."}')
    system = (
        "You plan slide decks for university teaching. From the material you pick what matters "
        "and lay it out as an outline, one entry per slide.\n"
        f"Write every title and gist in {SPRACHE.get(params.language, 'German')}.\n"
        "Decide yourself how many slides the material carries: one chapter usually makes 10 to 20 "
        f"slides, more material makes more. The deck has at least {lo} and at most {hi} slides in "
        "total. The first is the cover (role deckblatt), the last is the closing slide (role "
        "abschluss). For every slide in between choose one of these roles:\n"
        f"{rollen_text}\n"
        "Vary the roles: never the same role on two neighbouring slides except text, and use every "
        "role at least once when the material allows. Roles with an illustration suit topics a "
        "picture can explain, not definitions.\n"
        f"{nummern}"
        'Answer with one JSON object only: {"title": "...", "subtitle": "...", "slides": '
        f'[{eintrag}]}}. The gist is one sentence saying what '
        "the slide shows."
    )
    aufgabe = f"FACTS:\n{source}\n" if mit_nummern else f"MATERIAL:\n{source}\n"
    if params.instructions.strip():
        aufgabe += f"\nINSTRUCTION FROM THE TEACHER: {params.instructions.strip()}"
    return [{"role": "system", "content": system}, {"role": "user", "content": aufgabe}]


def _mische_paare(paare: list[tuple[str, object]]) -> dict:
    """Concatenate duplicate keys whose values are lists and merge those whose values are dicts, so a model repeating a key never loses everything but the last value to plain json.loads."""
    objekt: dict = {}
    for schluessel, wert in paare:
        vorhanden = objekt.get(schluessel)
        if schluessel in objekt and isinstance(vorhanden, list) and isinstance(wert, list):
            objekt[schluessel] = vorhanden + wert
        elif schluessel in objekt and isinstance(vorhanden, dict) and isinstance(wert, dict):
            objekt[schluessel] = {**vorhanden, **wert}
        else:
            objekt[schluessel] = wert
    return objekt


def json_objekt(raw: str) -> dict:
    """The one JSON object in the answer, fences and chatter stripped."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise Unusable("keine JSON-Klammern in der Antwort")
    try:
        data = json.loads(text[start:end + 1], object_pairs_hook=_mische_paare)
    except json.JSONDecodeError as exc:
        raise Unusable(f"kein gültiges JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise Unusable("die Antwort ist kein Objekt")
    return data


def _nummern(roh, gueltig: set[int] | None) -> list[int]:
    """The fact numbers of one entry, anything that is not a known number drops out."""
    if not isinstance(roh, list):
        return []
    aus: list[int] = []
    for wert in roh:
        try:
            nummer = int(wert)
        except (TypeError, ValueError):
            continue
        if (gueltig is None or nummer in gueltig) and nummer not in aus:
            aus.append(nummer)
    return aus


def parse_answer(raw: str, rollen: list[str], gueltig: set[int] | None = None) -> Outline:
    """The outline out of the answer. ``gueltig`` are the numbers the fact pool really holds."""
    data = json_objekt(raw)
    roh = data.get("slides")
    if not isinstance(roh, list) or not roh:
        raise Unusable("die Antwort enthält keine Folien")
    rows: list[OutlineRow] = []
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            continue
        titel = str(eintrag.get("title") or "").strip()
        if not titel:
            continue
        rows.append(OutlineRow(role=str(eintrag.get("role") or "text").strip().lower(),
                               title=titel[:120], gist=str(eintrag.get("gist") or "").strip()[:300],
                               fact_ids=_nummern(eintrag.get("fact_ids"), gueltig)))
    titel = str(data.get("title") or (rows[0].title if rows else "")).strip()[:120]
    outline = Outline(title=titel, subtitle=str(data.get("subtitle") or "").strip()[:160], rows=rows)
    return pruefe(outline, rollen)


def pruefe(outline: Outline, rollen: list[str], bounds: tuple[int, int] | None = None) -> Outline:
    """Cover first, closing last, no role twice in a row, count within the given bounds or the standard ones."""
    lo, hi = bounds or FOLIEN_GRENZEN
    rows = [r.model_copy() for r in outline.rows if r.title.strip()]
    if len(rows) < lo:
        raise Unusable(f"nur {len(rows)} Folien, verlangt sind mindestens {lo}")
    rows = rows[:hi]
    erlaubt = [r for r in WAEHLBARE_ROLLEN if r in rollen] or ["text"]
    for r in rows:
        if r.role not in erlaubt:
            r.role = "text"
    rows[0].role = "deckblatt"
    rows[-1].role = "abschluss"
    for i in range(1, len(rows) - 1):
        vorher = rows[i - 1].role
        if rows[i].role == vorher and vorher != "text":
            ersatz = [r for r in ("text_mit_bild", "zwei_spalten", "text", "bild_gross", "abschnitt")
                      if r in erlaubt and r != vorher]
            rows[i].role = ersatz[0] if ersatz else "text"
    return Outline(title=outline.title or rows[0].title, subtitle=outline.subtitle, rows=mit_ids(rows))


def mit_ids(rows: list[OutlineRow]) -> list[OutlineRow]:
    """Fresh ids only where one is missing or repeated, so slides keep their content."""
    hoechste = max((int(r.id[1:]) for r in rows if _ID.match(r.id or "")), default=0)
    gesehen: set[str] = set()
    out: list[OutlineRow] = []
    for r in rows:
        rid = r.id if _ID.match(r.id or "") and r.id not in gesehen else ""
        if not rid:
            hoechste += 1
            rid = f"s{hoechste}"
        gesehen.add(rid)
        out.append(OutlineRow(id=rid, role=r.role, title=r.title, gist=r.gist,
                              fact_ids=list(r.fact_ids)))
    return out


def regen_messages(row: OutlineRow, outline: Outline, params: PraesentationParams,
                   verlauf: list[dict], quelle: str) -> list[dict]:
    """One entry revised to a wish, folded into a single user turn like the podcast's refine call."""
    system = (
        "You revise one entry of a slide deck outline. Keep its role and its place. "
        f"Write in {SPRACHE.get(params.language, 'German')}. Answer with one JSON object only: "
        '{"title": "...", "gist": "..."}.'
    )
    plan = "\n".join(f"{i + 1}. [{r.role}] {r.title}: {r.gist}" for i, r in enumerate(outline.rows))
    user = (f"OUTLINE:\n{plan}\n\nENTRY TO REVISE: [{row.role}] {row.title}: {row.gist}\n\n"
            f"MATERIAL EXCERPT:\n{quelle[:4000]}")
    if len(verlauf) > 1:
        austausch = "\n".join(
            f"{'teacher' if m.get('role') == 'user' else 'assistant'}: {m.get('content', '')}"
            for m in verlauf[:-1]
        )
        user += f"\n\nCONVERSATION SO FAR:\n{austausch}"
    if verlauf:
        wunsch = next((m.get("content", "") for m in reversed(verlauf) if m.get("role") == "user"), "")
        user += f"\n\nWISH OF THE TEACHER: {wunsch}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_row(raw: str) -> tuple[str, str]:
    data = json_objekt(raw)
    titel = str(data.get("title") or "").strip()[:120]
    if not titel:
        raise Unusable("die Antwort hat keinen Titel")
    return titel, str(data.get("gist") or "").strip()[:300]
