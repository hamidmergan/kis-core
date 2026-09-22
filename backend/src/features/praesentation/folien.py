"""The content call per batch of slides, and the parsing of the answer into slides."""

from __future__ import annotations

import re

from src.features.praesentation.gliederung import SPRACHE, Unusable, json_objekt
from src.features.praesentation.schemas import (
    CHART_TYPES, MAX_CHART_CATEGORIES, MAX_CHART_SERIES, MAX_HEADING_CHARS, MAX_NOTES_CHARS, MAX_PROMPT_CHARS,
    MAX_SERIES_NAME_CHARS, MAX_SUBTITLE_CHARS, MAX_TABLE_ROWS, MAX_TEXT_ITEMS, MAX_TITLE_CHARS,
    Body, Column, ImageSpec, OutlineRow, PraesentationParams, Series, Slide,
)


def build_messages(source: str, params: PraesentationParams, rows: list[OutlineRow],
                   formen: dict[str, dict]) -> list[dict]:
    """The content call for one batch of slides."""
    lang = SPRACHE.get(params.language, "German")
    quelle_regel = "from the material only.\n"
    system = (
        f"You write the content of slides for university teaching, {quelle_regel}"
        f"Write all slide text in {lang}. Write image prompts in English.\n"
        "For every slide you get its role, title, gist and the fields of its layout with a word "
        "limit each. Fill exactly these fields:\n"
        "- title: the heading, within its word limit\n"
        "- subtitle: only when asked, one line\n"
        "- body: when the slide has one text field. kind is one of the allowed kinds.\n"
        '  bullets: {"kind": "bullets", "items": [...]} with 3 to 6 short points, all together within the word limit.\n'
        '  table: {"kind": "table", "header": [...], "rows": [[...]]} only for real value pairs from the material, at most 6 rows.\n'
        '  chart: {"kind": "chart", "chart_type": "bar|line|pie", "categories": [...], "series": [{"name": "...", "values": [numbers]}]} only for numbers with a shared unit, at most 6 categories.\n'
        '  image: {"kind": "image", "prompt": "..."} only when allowed, at most on every fourth slide.\n'
        '- columns: when the slide has two or more text fields, one entry per field: {"heading": "...", "items": [...]}\n'
        '- images: one entry per image field: {"prompt": "..."}, an English description of a scene or object, never text, letters or logos\n'
        "- notes: speaker notes of 60 to 120 words in the slide language, only when asked, else an empty string\n"
        'Answer with one JSON object only: {"slides": [{"id": "...", "title": "...", "subtitle": "...", '
        '"body": {...}, "columns": [...], "images": [...], "notes": "..."}]}.\n'
        'Every slide object goes inside that one "slides" array, nothing else at the top level.'
    )
    teile = []
    for r in rows:
        f = formen[r.id]
        # A slide asked for by instruction alone arrives without a heading, the model writes it.
        titelteil = f'title "{r.title}"' if r.title else "no title yet, write one"
        zeilen = [f"SLIDE {r.id} (role {r.role}): {titelteil}, gist: {r.gist}",
                  f"  title limit: {f['ueberschrift']} words"]
        if r.role in ("deckblatt", "abschluss") and f["zwischentitel"]:
            zeilen.append(f"  subtitle: yes, up to {f['zwischentitel'][0]} words")
        if len(f["fliesstexte"]) == 1:
            zeilen.append(f"  body: up to {f['fliesstexte'][0]} words, allowed kinds: {', '.join(f['body_kinds'])}")
        elif len(f["fliesstexte"]) > 1:
            grenzen = ", ".join(str(w) for w in f["fliesstexte"])
            kopf = f", each with a heading of up to {f['zwischentitel'][0]} words" if f["zwischentitel"] else ""
            zeilen.append(f"  columns: {len(f['fliesstexte'])} fields with word limits {grenzen}{kopf}")
        if f["bilder"]:
            zeilen.append(f"  images: {f['bilder']}")
        zeilen.append(f"  notes: {'yes' if params.notes else 'no'}")
        teile.append("\n".join(zeilen))
    kopf = f"MATERIAL:\n{source}\n\n"
    user = f"{kopf}SLIDES TO WRITE:\n" + "\n".join(teile)
    if params.instructions.strip():
        user += f"\n\nINSTRUCTION FROM THE TEACHER: {params.instructions.strip()}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_answer(raw: str, rows: list[OutlineRow], formen: dict[str, dict],
                 notizen: bool = False) -> list[Slide]:
    data = json_objekt(raw)
    nach_id = _kandidaten(data)
    if not nach_id:
        raise Unusable("die Antwort enthält keine Folien")
    slides: list[Slide] = []
    for r in rows:
        e = nach_id.get(r.id)
        if e is None:
            raise Unusable(f"Folie {r.id} fehlt in der Antwort")
        s = _slide(r, e, formen[r.id])
        # Speaker notes were asked for, so a slide without them is an unusable answer, not a slide.
        if notizen and not s.notes:
            raise Unusable(f"Folie {r.id} ohne Sprechtext")
        slides.append(s)
    return slides


def _kandidaten(data: dict) -> dict[str, dict]:
    """Every dict with an id anywhere in the parsed answer, so a slide the model placed outside the "slides" array is still found, with the "slides" array preferred whenever an id turns up in both."""
    andernorts: dict[str, dict] = {}
    aus_liste: dict[str, dict] = {}

    def sammeln(knoten: object, ziel: dict[str, dict]) -> None:
        if isinstance(knoten, dict):
            if "id" in knoten:
                schluessel = str(knoten.get("id"))
                if schluessel not in ziel:
                    ziel[schluessel] = knoten
                return  # accepted as a slide, its own fields are not searched for further ids
            for k, v in knoten.items():
                sammeln(v, aus_liste if k == "slides" else andernorts)
        elif isinstance(knoten, list):
            for eintrag in knoten:
                sammeln(eintrag, ziel)

    sammeln(data, andernorts)
    return {**andernorts, **aus_liste}


def _text(v) -> str:
    return str(v).strip() if isinstance(v, (str, int, float)) else ""


def _items(v) -> list[str]:
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if not isinstance(v, list):
        return []
    return [_text(x) for x in v if _text(x)][:MAX_TEXT_ITEMS]


def _zahl(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _slide(row: OutlineRow, e: dict, form: dict) -> Slide:
    s = Slide(id=row.id, role=row.role, title=_text(e.get("title"))[:MAX_TITLE_CHARS] or row.title,
              subtitle=_text(e.get("subtitle"))[:MAX_SUBTITLE_CHARS], notes=_text(e.get("notes"))[:MAX_NOTES_CHARS])
    n = len(form["fliesstexte"])
    if n == 1:
        s.body = _body(e.get("body"), form["body_kinds"])
    elif n > 1:
        cols = e.get("columns") if isinstance(e.get("columns"), list) else []
        s.columns = [Column(heading=_text(c.get("heading"))[:MAX_HEADING_CHARS], items=_items(c.get("items")))
                     for c in cols[:n] if isinstance(c, dict)]
        while len(s.columns) < n:
            s.columns.append(Column())
    bilder = e.get("images") if isinstance(e.get("images"), list) else []
    s.images = [ImageSpec(prompt=_text(b.get("prompt"))[:MAX_PROMPT_CHARS]) for b in bilder[:form["bilder"]]
                if isinstance(b, dict) and _text(b.get("prompt"))]
    while len(s.images) < form["bilder"]:
        s.images.append(ImageSpec(prompt=s.title))
    return s


def _body(roh, kinds: list[str]) -> Body:
    """A body of an allowed kind, anything broken becomes bullets."""
    if not isinstance(roh, dict):
        return Body(kind="bullets", items=_items(roh))
    kind = str(roh.get("kind") or "bullets")
    if kind not in kinds:
        kind = "bullets"
    b = Body(kind=kind, items=_items(roh.get("items")))
    if kind == "table":
        b.header = _items(roh.get("header"))
        b.rows = [_items(z) for z in (roh.get("rows") or []) if isinstance(z, list)][:MAX_TABLE_ROWS]
        b.rows = [z for z in b.rows if z]
        if not b.rows:
            b.kind = "bullets"
    elif kind == "chart":
        b.chart_type = str(roh.get("chart_type") or "bar")
        if b.chart_type not in CHART_TYPES:
            b.chart_type = "bar"
        b.categories = _items(roh.get("categories"))[:MAX_CHART_CATEGORIES]
        for serie in (roh.get("series") or [])[:MAX_CHART_SERIES]:
            if isinstance(serie, dict):
                werte = [_zahl(v) for v in (serie.get("values") or [])][:len(b.categories)]
                werte += [0.0] * (len(b.categories) - len(werte))
                b.series.append(Series(name=_text(serie.get("name"))[:MAX_SERIES_NAME_CHARS], values=werte))
        if not b.categories or not b.series:
            b.kind = "bullets"
    elif kind == "image":
        b.prompt = _text(roh.get("prompt"))[:MAX_PROMPT_CHARS]
        if not b.prompt:
            b.kind = "bullets"
    return b


def regen_messages(slide: Slide, row: OutlineRow, form: dict, params: PraesentationParams,
                   verlauf: list[dict], selected_text: str, quelle: str) -> list[dict]:
    """One slide revised to a wish, folded into a single user turn like the outline's refine call."""
    basis = build_messages(quelle, params, [row], {row.id: form})
    bisher = slide.model_dump_json(exclude={"layout"})
    zusatz = f"\n\nCURRENT SLIDE (revise it, keep the id):\n{bisher}"
    if selected_text.strip():
        zusatz += f"\n\nTHE TEACHER MARKED THIS PART: {selected_text.strip()}"
    if len(verlauf) > 1:
        austausch = "\n".join(
            f"{'teacher' if m.get('role') == 'user' else 'assistant'}: {m.get('content', '')}"
            for m in verlauf[:-1]
        )
        zusatz += f"\n\nCONVERSATION SO FAR:\n{austausch}"
    if verlauf:
        wunsch = next((m.get("content", "") for m in reversed(verlauf) if m.get("role") == "user"), "")
        zusatz += f"\n\nWISH OF THE TEACHER: {wunsch}"
    basis[1]["content"] += zusatz
    return basis


def inhaltswoerter(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\w{5,}", text)}


def source_excerpt(source: str, needles: list[str], limit: int) -> str:
    """The stretch of the material that shares most words with the needles."""
    if len(source) <= limit:
        return source
    woerter = set().union(*(inhaltswoerter(n) for n in needles if n))
    if not woerter:
        return source[:limit]
    schritt = max(200, limit // 2)
    beste, wert = 0, -1
    for start in range(0, len(source), schritt):
        treffer = len(woerter & inhaltswoerter(source[start:start + limit]))
        if treffer > wert:
            beste, wert = start, treffer
    return source[beste:beste + limit]
