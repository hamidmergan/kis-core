"""The outline call: prompt, parsing, and the rules that keep a deck varied."""

from __future__ import annotations

import json
import re
from typing import Callable

from src.features.praesentation.schemas import (
    FOLIEN_GRENZEN, WAEHLBARE_ROLLEN, Outline, OutlineRow, PraesentationParams,
)

_ROLLE_TEXT = {
    "abschnitt": "a section divider with only a heading",
    "text": ("a heading with bullet points, or where the content has that shape a table, a chart, cards with "
             "icons for parallel topics, bars for durations or shares, or one highlighted key figure"),
    "zwei_spalten": "a heading with two or more columns, each with its own subheading",
    "text_mit_bild": "a heading, bullet points and one or more illustrations",
    "bild_gross": "a heading and one or more large illustrations, no text",
}
SPRACHE = {"de": "German", "en": "English"}
_ID = re.compile(r"^s\d+$")


# One slide per this many characters on top of the base, about what NotebookLM builds.
_ZEICHEN_JE_FOLIE = 60_000
_GRUND_FOLIEN = 8
# Slides with an illustration cost minutes each to draw, at most one in this many carries one.
_BILD_JEDE = 5
_BILD_ROLLEN = ("text_mit_bild", "bild_gross")
# Cover, overview and closing draw on all files, the other slides are shared out among them.
RAHMEN_FOLIEN = 3


def ziel_folien(zeichen: int) -> int:
    """How many slides the material carries, a target the planner may deviate from."""
    lo, hi = FOLIEN_GRENZEN
    return max(lo, min(hi, _GRUND_FOLIEN + zeichen // _ZEICHEN_JE_FOLIE))


class Unusable(RuntimeError):
    """The answer was not a usable outline, the caller may try once more."""


def build_messages(material: str, params: PraesentationParams, rollen: list[str],
                   modus: str = "stellen", *, dateien: list[str] | None = None,
                   ziel: int | None = None, fehlt: list[str] | None = None,
                   schief: list[str] | None = None,
                   anteile: dict[str, int] | None = None) -> list[dict]:
    """The outline call, one entry per slide, planned over the numbered material."""
    from src.services.text_map import hinweis

    lo, hi = FOLIEN_GRENZEN
    rollen_text = "\n".join(f"- {r}: {_ROLLE_TEXT[r]}" for r in rollen if r in _ROLLE_TEXT)
    eintrag = '{"role": "...", "title": "...", "gist": "...", "refs": [12, "14-17"]}'
    system = (
        "You plan slide decks for university teaching. From the material you pick what matters "
        "and lay it out as an outline, one entry per slide. Each title states the message of "
        "its slide, not only its topic.\n"
        f"Write every title and gist in {SPRACHE.get(params.language, 'German')}.\n"
        + (f"Plan around {ziel} slides for this amount of material. " if ziel else
           "Decide yourself how many slides the material carries: one chapter usually makes "
           "10 to 20 slides, more material makes more. ")
        + f"The deck has at least {lo} and at most {hi} slides in "
        "total. The first is the cover (role deckblatt), the last is the closing slide (role "
        "abschluss). The closing slide's title is the one thought the audience takes home, "
        "never a thank-you. For every slide in between choose one of these roles:\n"
        f"{rollen_text}\n"
        "Vary the roles: never the same role on two neighbouring slides except text, and use every "
        "role at least once when the material allows. Roles with an illustration suit topics a "
        "picture can explain, not definitions.\n"
        f"{hinweis(modus)} Every slide carries its own refs, the slides together cover "
        "what matters in the whole material. Work through the material to its last number "
        "before you settle the slides. A slide that draws on everything, such as an agenda "
        "or the closing slide, carries an empty list.\n"
        + (f"The material comes from {len(dateien)} files: {', '.join(dateien)}. EVERY one of "
           "them gets slides of its own. "
           + ("Give each file exactly this many slides besides cover, overview and closing: "
              + ", ".join(f"{d}: {n}" for d, n in anteile.items())
              + ". A slide that brings several documents together counts for the file it draws "
              "on most. " if anteile else
              "Balance the slides between the files: a large file gets more than a small one, "
              "but never more than twice the slides of the smallest. ")
           + "Where documents touch the same subject, bring them together. The slide before the "
           "closing one is an overview that compares the documents along the same points: what "
           "each requires, its deadlines, who is responsible and the consequences. It has "
           "role text and a gist that asks for a table.\n"
           if dateien and len(dateien) > 1 else "")
        + 'Answer with one JSON object only: {"title": "...", "subtitle": "...", "slides": '
        f'[{eintrag}]}}. The gist is one sentence saying what '
        "the slide shows."
    )
    aufgabe = f"/no_think\nMATERIAL:\n{material}\n"
    if params.instructions.strip():
        aufgabe += f"\nINSTRUCTION FROM THE TEACHER: {params.instructions.strip()}"
    if fehlt:
        aufgabe += ("\nYOUR LAST OUTLINE GAVE THESE FILES FAR TOO LITTLE ROOM. Give each a "
                    "share of the slides that matches how much of the material it holds: "
                    + ", ".join(fehlt))
    if schief:
        aufgabe += ("\nYOUR LAST OUTLINE WAS UNBALANCED: " + ", ".join(schief)
                    + ". Keep to the number of slides given for each file.")
    return [{"role": "system", "content": system}, {"role": "user", "content": aufgabe}]


def folien_je_datei(karte, n: int) -> dict[str, int]:
    """How many of ``n`` slides each file gets: at least two, more for longer files, never more than twice the smallest.

    Empty for a single file or when there are fewer slides than files.
    """
    gewicht = {q.dateiname: len(q.stuecke) for q in karte.sources if q.stuecke}
    if len(gewicht) < 2 or n < len(gewicht):
        return {}
    zahl = dict.fromkeys(gewicht, min(2, n // len(gewicht)))
    for _ in range(n - sum(zahl.values())):
        grenze = 2 * min(zahl.values())
        d = max((d for d in gewicht if zahl[d] < grenze), key=lambda d: gewicht[d] / zahl[d])
        zahl[d] += 1
    return zahl


def schief(rows: list[OutlineRow], karte) -> list[str]:
    """The files whose slides miss their share by more than one, empty when the deck is balanced.

    A slide counts for the file most of its passages come from.
    """
    ist = {q.dateiname: 0 for q in karte.sources if q.stuecke}
    for r in rows:
        quellen = [karte.stelle(n).source for n in r.stellen if 1 <= n <= len(karte)]
        if quellen:
            haupt = max(set(quellen), key=quellen.count)
            ist[karte.sources[haupt].dateiname] += 1
    soll = folien_je_datei(karte, sum(ist.values()))
    return [f"{d}: {ist[d]} slides instead of {n}" for d, n in soll.items() if abs(ist[d] - n) > 1]


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



def parse_answer(raw: str, rollen: list[str],
                 stellen: Callable[[object], list[int]] | None = None) -> Outline:
    """The outline out of the answer, ``stellen`` turns an entry's refs into passages."""
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
                               title=titel[:120],
                               gist=str(eintrag.get("gist") or "").strip()[:300],
                               stellen=stellen(eintrag.get("refs")) if stellen else []))
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
    # Pictures only where the cap allows, the rest of those slides keep their text.
    frei = len(rows) // _BILD_JEDE
    for r in rows[1:-1]:
        if r.role in _BILD_ROLLEN:
            if frei > 0:
                frei -= 1
            else:
                r.role = "text"
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
                              stellen=list(r.stellen)))
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
            f"MATERIAL EXCERPT:\n{quelle}")
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
