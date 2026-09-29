"""The content call per batch of slides, and the parsing of the answer into slides."""

from __future__ import annotations

import re

from src.features.praesentation import icons
from src.features.praesentation.gliederung import SPRACHE, Unusable, json_objekt
from src.features.praesentation.raster import (
    MAX_BALKEN, MAX_KARTEN, MAX_KENNZAHLEN, MAX_SCHRITTE, MAX_STUFEN, MAX_SYMBOLE,
)
from src.limits import PRAESENTATION_SLIDE_CONTEXT_CHARS
from src.features.praesentation.schemas import (
    CHART_TYPES, MAX_BAR_TEXT_CHARS, MAX_CHART_CATEGORIES, MAX_CHART_SERIES, MAX_GIST_CHARS, MAX_HEADING_CHARS,
    MAX_KEY_CHARS, MAX_NOTES_CHARS, MAX_PROMPT_CHARS, MAX_SERIES_NAME_CHARS, MAX_SUBTITLE_CHARS, MAX_TABLE_ROWS,
    MAX_TEXT_ITEMS, MAX_TITLE_CHARS, Bar, Body, Card, Column, Entry, Figure, ImageSpec, OutlineRow,
    PraesentationParams, Series, Slide, Symbol,
)

# A slide below these reads as empty, a small field asks for fewer, at about twelve words a point.
MIN_STICHPUNKTE = 4
MIN_JE_SPALTE = 3
WOERTER_JE_PUNKT = 12
# Cards on nearly every slide read as a template, every third slide that could carry them is enough.
KARTEN_JEDE = 3
# Below these counts a drawing says less than a line of text.
MIN_KENNZAHLEN = 2
MIN_SCHRITTE = 2
MIN_STUFEN = 3
MIN_SYMBOLE = 3
# A number in a bar's text, its thousands and decimal marks included.
_ZAHL = re.compile(r"\d(?:[.,  ]?\d)*")
# The lists a drawn body keeps its entries in, in the order a broken answer is searched for them.
_LISTEN = ("cards", "bars", "steps", "levels", "figures", "symbols")


def material_je_folie(rows: list[OutlineRow], karte, alle: list[OutlineRow]) -> dict[str, str]:
    """Je Folie die Stellen aus dem Originaltext, auf denen sie ruht, mit ihren Nachbarn.

    Eine Zeile ohne Stellen ist eine Agenda oder ein Schluss, sie ruht auf allem. Sie
    bekommt deshalb den Plan des ganzen Decks statt einzelner Stellen.
    """
    from src.limits import MAP_PASSAGE_NEIGHBOURS

    aus: dict[str, str] = {}
    for r in rows:
        if r.stellen:
            aus[r.id] = karte.passagen(r.stellen, nachbarn=MAP_PASSAGE_NEIGHBOURS,
                                       budget=PRAESENTATION_SLIDE_CONTEXT_CHARS)
        else:
            aus[r.id] = "the plan of the whole deck:\n" + "\n".join(
                f"- {a.title}: {a.gist}" for a in alle if a.id != r.id)
    return aus


def build_messages(source: str, params: PraesentationParams, rows: list[OutlineRow],
                   formen: dict[str, dict], fakten: dict[str, str] | None = None) -> list[dict]:
    """The content call for one batch of slides.

    With ``fakten`` every slide carries its own passages of the original text, and the
    shared material block goes away.
    """
    lang = SPRACHE.get(params.language, "German")
    quelle_regel = ("from its own material only. Each slide below carries the passages of "
                    "the original text it rests on, and you never use the material of another "
                    "slide.\n") if fakten else "from the material only.\n"
    system = (
        f"You write the content of slides for university teaching, {quelle_regel}"
        f"Write all slide text in {lang}. Write image prompts in English.\n"
        "For every slide you get its role, title, gist and the fields of its layout with a word "
        "limit each. Fill exactly these fields:\n"
        "- title: the heading, within its word limit\n"
        "- subtitle: only when asked, one line\n"
        "- body: when the slide has one text field. kind is one of the allowed kinds.\n"
        '  bullets: {"kind": "bullets", "items": [...]} with 5 to 7 short points, all together within the word limit. Fewer points are not worth a slide.\n'
        '  table: {"kind": "table", "header": [...], "rows": [[...]]} for real value pairs from the material or things compared along the same attributes, at most 6 rows. A table stands alone: no bullet points beside it.\n'
        '  chart: {"kind": "chart", "chart_type": "bar|line|pie", "categories": [...], "series": [{"name": "...", "values": [numbers]}]} only for numbers with a shared unit, at most 6 categories.\n'
        '  cards: {"kind": "cards", "cards": [{"icon": "...", "title": "...", "text": "..."}]} for two or more '
        "ideas of equal weight, each a short title and one sentence. icon is one name from this list: "
        f"{', '.join(icons.namen())}.\n"
        '  bars: {"kind": "bars", "bars": [{"label": "...", "value": number, "text": "..."}]} a bar chart, only to compare '
        "one measure across named things, where a longer bar means more of the same, such as shares per group or the "
        'length of several periods. text is the number with its unit, such as "45 %" or "until 2028". Never for a list '
        "without numbers, never when all values are equal, never for limits of different kinds, those are figures.\n"
        '  figures: {"kind": "figures", "figures": [{"value": "...", "label": "..."}]} for two to four numbers that '
        "carry the slide, such as limits, deadlines, amounts or durations: value is the number with its unit, at most "
        '10 characters, such as "8 h" or "25,000 €", label says in a few words what it counts. Numbers of different '
        "kinds, such as a time limit beside a deadline, are figures, never bars or levels.\n"
        '  steps: {"kind": "steps", "steps": [{"title": "...", "text": "..."}]} only for a real sequence in which each '
        "step follows the one before, such as a procedure, a lab protocol or the phases of a project, in that order: "
        "title names the step in one to three words, text is one short sentence. Never for topics of one field that "
        "stand side by side.\n"
        '  levels: {"kind": "levels", "levels": [{"title": "...", "text": "..."}]} only for a true rank order in which '
        "each level stands above the next, the highest first, such as a hierarchy of norms or of needs: title names the "
        "level, text is one short sentence. Never for limits, rules or a list whose order means nothing.\n"
        '  symbols: {"kind": "symbols", "symbols": [{"icon": "...", "label": "..."}]} for three or more terms of one '
        "set that need no explanation, such as protected characteristics or fields of work: label is the bare term "
        "in one to three words, no sentence and no reference in parentheses, icon a name from the list of cards "
        "that fits the term.\n"
        '  highlight: {"kind": "highlight", "key": "...", "text": "...", "emphasis": "..."} for one number or word '
        "that carries the slide: key is that number or word, at most 12 characters, text one sentence "
        "about it, emphasis a term that stands word for word in that sentence and gets marked in colour. Rare, only for a central figure.\n"
        "  cards, bars, figures, steps, levels, symbols and highlight only where the material has that shape, "
        "bullets stay the usual kind. In one answer each of these forms goes to one slide at most, so no two slides "
        "look alike.\n"
        "  The numbers of a table, chart, bars, figures or highlight belong to the slide's own title and gist, "
        "never to a neighbouring passage about something else.\n"
        '  image: {"kind": "image", "prompt": "..."} only when allowed, at most on every fourth slide.\n'
        '- columns: when the slide has two or more text fields, one entry per field: {"heading": "...", "items": [...]}\n'
        '- images: one entry per image field: {"prompt": "..."}, an English description of a scene, object or visual '
        "metaphor. Never a diagram, chart, curve, formula, map, sign or screen, and never words, labels, numbers or "
        "letters in the picture: whatever needs labelling belongs in the slide text. The same holds for an image body.\n"
        "- notes: speaker notes of 60 to 120 words in the slide language, only when asked, else an empty string\n"
        'Answer with one JSON object only: {"slides": [{"id": "...", "title": "...", "subtitle": "...", '
        '"body": {...}, "columns": [...], "images": [...], "notes": "..."}]}.\n'
        'Every slide object goes inside that one "slides" array, nothing else at the top level.\n'
        "Where the material shows the numbered part a statement comes from, such as '§ 15 Abs. 4' "
        "or 'Art. 5', name it in parentheses at the end of the statement. The page lines of the "
        "material are never such a number."
    )
    teile = []
    for r in rows:
        f = formen[r.id]
        # A slide asked for by instruction alone arrives without a heading, the model writes it.
        titelteil = f'title "{r.title}"' if r.title else "no title yet, write one"
        zeilen = [f"SLIDE {r.id} (role {r.role}): {titelteil}, gist: {r.gist}",
                  f"  title limit: {f['ueberschrift']} words"
                  + (f", at most {f['ueberschrift_zeichen']} characters" if f.get("ueberschrift_zeichen") else "")]
        if r.role in ("deckblatt", "abschluss") and f["zwischentitel"]:
            zeilen.append(f"  subtitle: yes, up to {f['zwischentitel'][0]} words")
        if len(f["fliesstexte"]) == 1:
            zeilen.append(f"  body: up to {f['fliesstexte'][0]} words, allowed kinds: {', '.join(f['body_kinds'])}")
            if "cards" in f["body_kinds"] and f.get("karten"):
                k = f["karten"]
                zeilen.append(f"  cards: 2 to {k['max']}, each title up to {k['titel_woerter']} words, "
                              f"each text up to {k['text_woerter']} words")
            if "bars" in f["body_kinds"] and f.get("balken"):
                zeilen.append(f"  bars: 2 to {f['balken']}")
            if "figures" in f["body_kinds"] and f.get("kennzahlen", 0) >= MIN_KENNZAHLEN:
                zeilen.append(f"  figures: {MIN_KENNZAHLEN} to {f['kennzahlen']}")
            for art, name, mindest in (("steps", "schritte", MIN_SCHRITTE), ("levels", "stufen", MIN_STUFEN)):
                if art in f["body_kinds"] and f.get(name, {}).get("max", 0) >= mindest:
                    p = f[name]
                    zeilen.append(f"  {art}: {mindest} to {p['max']}, each title up to {p['titel_woerter']} words, "
                                  f"each text up to {p['text_woerter']} words")
            if "symbols" in f["body_kinds"] and f.get("symbole", 0) >= MIN_SYMBOLE:
                zeilen.append(f"  symbols: {MIN_SYMBOLE} to {f['symbole']}")
        elif len(f["fliesstexte"]) > 1:
            grenzen = ", ".join(str(w) for w in f["fliesstexte"])
            kopf = f", each with a heading of up to {f['zwischentitel'][0]} words" if f["zwischentitel"] else ""
            zeilen.append(f"  columns: {len(f['fliesstexte'])} fields with word limits {grenzen}{kopf}, "
                          "at least 3 points in each")
        if f["bilder"]:
            zeilen.append(f"  images: {f['bilder']}")
        zeilen.append(f"  notes: {'yes' if params.notes else 'no'}")
        eigene = (fakten or {}).get(r.id, "").strip()
        if eigene:
            zeilen.append("  material of this slide:\n" + eigene)
        teile.append("\n".join(zeilen))
    kopf = "" if fakten else f"MATERIAL:\n{source}\n\n"
    user = f"{kopf}SLIDES TO WRITE:\n" + "\n".join(teile)
    if params.instructions.strip():
        user += f"\n\nINSTRUCTION FROM THE TEACHER: {params.instructions.strip()}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def karten_folien(rows: list[OutlineRow], formen: dict[str, dict]) -> set[str]:
    """The slides that may carry cards, every third one of those whose layout allows them, in deck order."""
    moegliche = [r.id for r in rows if "cards" in formen.get(r.id, {}).get("body_kinds", [])]
    return set(moegliche[::KARTEN_JEDE])


def ohne_karten(form: dict) -> dict:
    return {**form, "body_kinds": [k for k in form["body_kinds"] if k != "cards"]}


def punkte(s: Slide) -> int:
    if s.body is not None and s.body.kind == "bullets":
        return len(s.body.items)
    return sum(len(c.items) for c in s.columns)


def zu_duenn(slides: list[Slide], formen: dict[str, dict]) -> dict[str, str]:
    """Per thin slide what is missing, a table, chart or cards stand on their own and never count."""
    aus: dict[str, str] = {}
    for s in slides:
        grenzen = formen[s.id]["fliesstexte"]
        if s.body is not None and s.body.kind == "bullets" and grenzen:
            mindest = min(MIN_STICHPUNKTE, grenzen[0] // WOERTER_JE_PUNKT)
            if len(s.body.items) < mindest:
                aus[s.id] = f"{len(s.body.items)} bullet points, it needs {mindest} to 7"
        elif s.columns and len(grenzen) == len(s.columns):
            mindest = [min(MIN_JE_SPALTE, g // WOERTER_JE_PUNKT) for g in grenzen]
            if any(len(c.items) < m for c, m in zip(s.columns, mindest)):
                zahlen = ", ".join(str(len(c.items)) for c in s.columns)
                aus[s.id] = f"columns with {zahlen} points, each needs at least {max(mindest)}"
    return aus


def nachfrage(nachrichten: list[dict], antwort: str, duenn: dict[str, str]) -> list[dict]:
    """The same call once more, with the thin slides named and asked for again."""
    zeilen = "\n".join(f"- {sid}: {grund}" for sid, grund in duenn.items())
    return [*nachrichten, {"role": "assistant", "content": antwort}, {"role": "user", "content": (
        f"These slides came out too thin:\n{zeilen}\nTheir material holds more statements. Write these "
        "slides again with more points taken from their own material, never invented, each point within "
        "the word limit. Answer with the same JSON object, holding only these slides.")}]


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
        s.body = _body(e.get("body"), form)
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


def _body(roh, form: dict) -> Body:
    """A body of an allowed kind, anything broken becomes bullets, every drawing capped at what its field holds."""
    kinds = form["body_kinds"]
    karten_max = (form.get("karten") or {}).get("max", MAX_KARTEN)
    balken_max = form.get("balken") or MAX_BALKEN
    schritte_max = (form.get("schritte") or {}).get("max", MAX_SCHRITTE)
    stufen_max = (form.get("stufen") or {}).get("max", MAX_STUFEN)
    kennzahlen_max = form.get("kennzahlen") or MAX_KENNZAHLEN
    symbole_max = form.get("symbole") or MAX_SYMBOLE
    if not isinstance(roh, dict):
        return Body(kind="bullets", items=_items(roh))
    kind = str(roh.get("kind") or "bullets")
    if kind not in kinds:
        # A drawing this slide may not carry keeps its content as points.
        return Body(kind="bullets", items=_items(roh.get("items")) or _als_punkte(roh))
    b = Body(kind=kind, items=_items(roh.get("items")))
    if kind == "table":
        b.header = _items(roh.get("header"))
        b.rows = [_items(z) for z in (roh.get("rows") or []) if isinstance(z, list)][:MAX_TABLE_ROWS]
        b.rows = [z for z in b.rows if z]
        if not b.rows:
            b.kind = "bullets"
        else:
            b.items = []
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
    elif kind == "cards":
        roh_karten = roh.get("cards") if isinstance(roh.get("cards"), list) else []
        b.cards = [Card(icon=icons.gueltig(k.get("icon")), title=_text(k.get("title"))[:MAX_HEADING_CHARS],
                        text=_text(k.get("text"))[:MAX_GIST_CHARS])
                   for k in roh_karten if isinstance(k, dict) and _text(k.get("title"))][:karten_max]
        if len(b.cards) < 2:
            b.kind, b.items = "bullets", b.items or [_zeile(k.title, k.text) for k in b.cards]
            b.cards = []
    elif kind == "bars":
        roh_balken = roh.get("bars") if isinstance(roh.get("bars"), list) else []
        b.bars = [Bar(label=_text(z.get("label"))[:MAX_HEADING_CHARS], value=_zahl(z.get("value")),
                      text=_text(z.get("text"))[:MAX_BAR_TEXT_CHARS])
                  for z in roh_balken if isinstance(z, dict) and _text(z.get("label"))][:balken_max]
        # A bar chart compares amounts, with fewer than two different ones it only repeats a label.
        if len(b.bars) < 2 or len({z.value for z in b.bars}) < 2:
            texte = {z.text for z in b.bars}
            b.kind, b.items = "bullets", b.items or [z.label if len(texte) == 1 else _zeile(z.label, z.text)
                                                     for z in b.bars]
            b.bars = []
        for z in b.bars:
            z.text = _mit_zahl(z.text, z.value)[:MAX_BAR_TEXT_CHARS]
    elif kind in ("steps", "levels"):
        eintraege = [Entry(title=_text(e.get("title"))[:MAX_HEADING_CHARS], text=_text(e.get("text"))[:MAX_GIST_CHARS])
                     for e in _liste(roh, kind) if _text(e.get("title"))]
        grenze, mindest = (schritte_max, MIN_SCHRITTE) if kind == "steps" else (stufen_max, MIN_STUFEN)
        eintraege = eintraege[:grenze]
        if len(eintraege) < mindest:
            b.kind, b.items = "bullets", b.items or [_zeile(e.title, e.text) for e in eintraege]
        else:
            setattr(b, kind, eintraege)
    elif kind == "figures":
        # A key figure is a number, a value without a digit was a word the model dressed up as one.
        b.figures = [Figure(value=_text(z.get("value"))[:MAX_KEY_CHARS], label=_text(z.get("label"))[:MAX_HEADING_CHARS])
                     for z in _liste(roh, kind) if re.search(r"\d", _text(z.get("value")))][:kennzahlen_max]
        if len(b.figures) < MIN_KENNZAHLEN:
            b.kind, b.items = "bullets", b.items or [_zeile(z.value, z.label) for z in b.figures]
            b.figures = []
    elif kind == "symbols":
        b.symbols = [Symbol(icon=icons.gueltig(z.get("icon")), label=_text(z.get("label"))[:MAX_HEADING_CHARS])
                     for z in _liste(roh, kind) if _text(z.get("label"))][:symbole_max]
        if len(b.symbols) < MIN_SYMBOLE:
            b.kind, b.items = "bullets", b.items or [z.label for z in b.symbols]
            b.symbols = []
    elif kind == "highlight":
        b.key = _text(roh.get("key"))[:MAX_KEY_CHARS]
        b.text = _text(roh.get("text"))[:MAX_GIST_CHARS]
        b.emphasis = _text(roh.get("emphasis"))[:MAX_HEADING_CHARS]
        # A term the sentence does not contain would mark nothing, so it is not kept.
        if b.emphasis.lower() not in b.text.lower():
            b.emphasis = ""
        if not b.key or not b.text:
            b.kind, b.items = "bullets", b.items or [t for t in (b.text or b.key,) if t]
            b.key = b.text = b.emphasis = ""
    return b


def _zeile(kopf: str, text: str) -> str:
    return f"{kopf}: {text}" if text else kopf


def _liste(roh: dict, name: str) -> list[dict]:
    return [e for e in (roh.get(name) if isinstance(roh.get(name), list) else []) if isinstance(e, dict)]


def _als_punkte(roh: dict) -> list[str]:
    """The entries of the first drawing list the answer holds, each as one point."""
    for name in _LISTEN:
        eintraege = _liste(roh, name)
        if eintraege:
            punkte = [_zeile(_text(e.get("value")), _text(e.get("label"))) if name == "figures"
                      else _zeile(_text(e.get("title") or e.get("label")), _text(e.get("text"))) for e in eintraege]
            return [p for p in punkte if p][:MAX_TEXT_ITEMS]
    return []


def _mit_zahl(text: str, wert: float) -> str:
    """A bar's text always shows its number, a text naming only the unit gets the number put in front."""
    zahl = f"{wert:g}"
    ziffern = re.sub(r"\D", "", zahl)
    if not text or any(re.sub(r"\D", "", z) == ziffern for z in _ZAHL.findall(text)):
        return text
    return f"{zahl} {text}"


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
