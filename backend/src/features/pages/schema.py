"""The page as data: which blocks exist, how long a text may be and how much fits on a page.

The model's answer and every save of the editor pass through the same cleaning, so a page
on disk always has a shape the frontend can draw. Nothing here is HTML, only plain text.
"""

from __future__ import annotations

import re

from src.limits import (
    PAGES_MAX_BLOCKS,
    PAGES_MAX_IMAGES,
    PAGES_MAX_ITEM_CHARS,
    PAGES_MAX_ITEMS,
    PAGES_MAX_LONG_CHARS,
    PAGES_MAX_SECTIONS,
    PAGES_MAX_SHORT_CHARS,
    PAGES_MAX_TABLE_COLS,
    PAGES_MAX_TABLE_ROWS,
)

VERSION = 1
KINDS = ("text", "bullets", "highlight", "cards", "steps", "figures", "bars", "table", "chart",
         "image", "mindmap", "wordcloud", "empty")
# A section the owner adds is a grid of fields, the key names the grid and the value its field count.
LAYOUTS = {"1": 1, "2": 2, "21": 2, "12": 2, "3": 3, "4": 4, "1-2": 3}
EMPTY = {"kind": "empty"}
# The languages a page is written or translated in.
LANGS = ("de", "en")
# "none" is the rule, a sign only where it tells cards apart. "info" is what older pages carry for none.
ICONS = ("none", "check", "x", "warning", "idea", "info")
# The looks a page can take, the frame call picks one, the frontend draws each differently.
DESIGNS = ("chapters", "timeline", "magazine", "guide")
CHART_TYPES = ("line", "bar")
MAX_FIGURES = 4
MAX_SERIES = 2
MAX_BRANCHES = 8
MAX_LEAVES = 5
MAX_WORDS = 24
# A category under a chart and a node of the mind map, longer ones no longer fit their place.
CHART_LABEL_CHARS = 24
MAP_LABEL_CHARS = 40
# A picture is only ever one the run stored in the job folder itself.
IMAGE_NAME = re.compile(r"^img_\d{1,3}\.(?:webp|png|jpg)$")
SECTION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def limits() -> dict:
    """What the editor enforces while typing, the same numbers this module cuts to."""
    return {
        "sections": PAGES_MAX_SECTIONS, "blocks": PAGES_MAX_BLOCKS, "images": PAGES_MAX_IMAGES,
        "tableRows": PAGES_MAX_TABLE_ROWS, "tableCols": PAGES_MAX_TABLE_COLS,
        "items": PAGES_MAX_ITEMS, "short": PAGES_MAX_SHORT_CHARS, "item": PAGES_MAX_ITEM_CHARS,
        "long": PAGES_MAX_LONG_CHARS, "imagePrompt": PAGES_MAX_LONG_CHARS,
        "series": MAX_SERIES, "branches": MAX_BRANCHES, "leaves": MAX_LEAVES, "words": MAX_WORDS,
        "label": CHART_LABEL_CHARS, "mapLabel": MAP_LABEL_CHARS,
    }


def text(value, most: int) -> str:
    """One line of plain text, cut at a word where possible."""
    if value is None or isinstance(value, (dict, list)):
        return ""
    # A spaced dash is not house style: before a capital it opens a subtitle, else it is a pause.
    s = " ".join(str(value).replace("**", "").split())
    s = re.sub(r"\s+[\u2013\u2014]\s+(?=[A-ZÄÖÜ])", ": ", s)
    s = re.sub(r"\s+[\u2013\u2014]\s+", ", ", s)
    if len(s) <= most:
        return s
    cut = s[:most].rsplit(" ", 1)[0]
    return (cut if len(cut) > most // 2 else s[:most]).rstrip(" ,;:")


def number(value) -> float | None:
    """A number from a number or a German or English numeral, None when it is none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value and abs(value) < 1e12 else None
    s = str(value or "").strip().replace("−", "-").replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return None
    return f if abs(f) < 1e12 else None


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _short(v) -> str:
    return text(v, PAGES_MAX_SHORT_CHARS)


def _item(v) -> str:
    return text(v, PAGES_MAX_ITEM_CHARS)


def _text_block(b: dict) -> dict | None:
    body = text(b.get("text"), PAGES_MAX_LONG_CHARS)
    return {"kind": "text", "text": body} if body else None


def _bullets(b: dict) -> dict | None:
    items = [s for s in (_item(i) for i in _list(b.get("items"))) if s][:PAGES_MAX_ITEMS]
    return {"kind": "bullets", "items": items} if items else None


# A key longer than this is a sentence, it goes in front of the text in normal type.
HIGHLIGHT_KEY_CHARS = 40


def _highlight(b: dict) -> dict | None:
    key, body = _short(b.get("key")), _item(b.get("text"))
    if len(key) > HIGHLIGHT_KEY_CHARS:
        key, body = "", _item(f"{key}. {body}".strip(" ."))
    return {"kind": "highlight", "key": key, "text": body} if key or body else None


def _cards(b: dict) -> dict | None:
    cards = []
    for c in _list(b.get("cards"))[:PAGES_MAX_ITEMS]:
        if not isinstance(c, dict):
            continue
        title, body = _short(c.get("title")), _item(c.get("text"))
        if title or body:
            icon = c.get("icon") if c.get("icon") in ICONS else "none"
            cards.append({"icon": icon, "title": title, "text": body})
    if not cards:
        return None
    out = {"kind": "cards", "cards": cards}
    if b.get("cols") == 1:
        out["cols"] = 1
    return out


def _steps(b: dict) -> dict | None:
    steps = []
    for s in _list(b.get("steps"))[:PAGES_MAX_ITEMS]:
        if isinstance(s, dict):
            title, body = _short(s.get("title")), _item(s.get("text"))
            if title or body:
                steps.append({"title": title, "text": body})
    return {"kind": "steps", "steps": steps} if steps else None


def _figures(b: dict) -> dict | None:
    figs = []
    for f in _list(b.get("figures"))[:MAX_FIGURES]:
        if isinstance(f, dict):
            value, label = text(f.get("value"), 24), _short(f.get("label"))
            if value:
                figs.append({"value": value, "label": label})
    return {"kind": "figures", "figures": figs} if figs else None


def _bars(b: dict) -> dict | None:
    bars = []
    for x in _list(b.get("bars"))[:PAGES_MAX_ITEMS]:
        if isinstance(x, dict):
            v = number(x.get("value"))
            label = _short(x.get("label"))
            if v is not None and v >= 0 and label:
                bars.append({"label": label, "value": v, "text": _item(x.get("text"))})
    if not bars:
        return None
    out: dict = {"kind": "bars", "bars": bars}
    top = number(b.get("max"))
    if top and top >= max(x["value"] for x in bars):
        out["max"] = top
    return out


def _table(b: dict) -> dict | None:
    header = [_short(h) for h in _list(b.get("header"))[:PAGES_MAX_TABLE_COLS]]
    rows = []
    for r in _list(b.get("rows"))[:PAGES_MAX_TABLE_ROWS]:
        if isinstance(r, list):
            cells = [_short(c) for c in r[:PAGES_MAX_TABLE_COLS]]
            if any(cells):
                rows.append(cells)
    cols = max([len(header)] + [len(r) for r in rows]) if rows else 0
    if cols < 2 or not rows:
        return None
    header = (header + [""] * cols)[:cols]
    rows = [(r + [""] * cols)[:cols] for r in rows]
    return {"kind": "table", "caption": _short(b.get("caption")), "header": header, "rows": rows}


def _chart(b: dict) -> dict | None:
    cats = [text(c, CHART_LABEL_CHARS) for c in _list(b.get("categories"))[:PAGES_MAX_ITEMS]]
    series = []
    for s in _list(b.get("series"))[:MAX_SERIES]:
        if not isinstance(s, dict):
            continue
        values = [number(v) for v in _list(s.get("values"))[:len(cats)]]
        if len(values) == len(cats) and all(v is not None for v in values):
            series.append({"name": _short(s.get("name")), "values": values})
    if len(cats) < 2 or not series:
        return None
    kind = b.get("chart_type") if b.get("chart_type") in CHART_TYPES else "bar"
    # A bar chart draws one series, a second one would silently vanish.
    if kind == "bar":
        series = series[:1]
    if any(v < 0 for s in series for v in s["values"]):
        return None
    return {"kind": "chart", "chart_type": kind, "caption": _short(b.get("caption")),
            "x_label": _short(b.get("x_label")), "y_label": _short(b.get("y_label")),
            "categories": cats, "series": series}


def _image(b: dict) -> dict | None:
    src = str(b.get("src") or "")
    if not IMAGE_NAME.match(src):
        return None
    return {"kind": "image", "src": src, "alt": _short(b.get("alt")),
            "prompt": text(b.get("prompt"), PAGES_MAX_LONG_CHARS), "caption": _short(b.get("caption"))}


def _mindmap(b: dict) -> dict | None:
    branches = []
    for br in _list(b.get("branches"))[:MAX_BRANCHES]:
        if not isinstance(br, dict):
            continue
        title = text(br.get("title"), MAP_LABEL_CHARS)
        if not title:
            continue
        to = str(br.get("to") or "")
        leaves = [s for s in (text(x, MAP_LABEL_CHARS) for x in _list(br.get("leaves"))[:MAX_LEAVES]) if s]
        branches.append({"title": title, "to": to if SECTION_ID.match(to) else "", "leaves": leaves})
    center = text(b.get("center"), MAP_LABEL_CHARS)
    if not center or len(branches) < 2:
        return None
    return {"kind": "mindmap", "center": center, "caption": _short(b.get("caption")),
            "branches": branches}


def _wordcloud(b: dict) -> dict | None:
    words = []
    for w in _list(b.get("words"))[:MAX_WORDS]:
        if isinstance(w, list) and len(w) == 2:
            word, n = text(w[0], MAP_LABEL_CHARS), number(w[1])
            if word and n is not None and n > 0:
                words.append([word, int(n)])
    words.sort(key=lambda w: -w[1])
    if len(words) < 3:
        return None
    return {"kind": "wordcloud", "caption": _short(b.get("caption")), "words": words}


_CLEAN = {"text": _text_block, "bullets": _bullets, "highlight": _highlight, "cards": _cards, "steps": _steps,
          "figures": _figures, "bars": _bars, "table": _table, "chart": _chart, "image": _image,
          "mindmap": _mindmap, "wordcloud": _wordcloud}


def clean_block(raw) -> dict | None:
    """One block in its known shape, None for anything unknown or empty."""
    if not isinstance(raw, dict) or raw.get("kind") not in _CLEAN:
        return None
    return _CLEAN[raw["kind"]](raw)


def _section(raw, taken: set[str], index: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    sid = str(raw.get("id") or "")
    if not SECTION_ID.match(sid) or sid in taken:
        sid = f"s{index + 1}"
        while sid in taken:
            sid += "x"
    layout = raw.get("layout") if raw.get("layout") in LAYOUTS and not raw.get("hero") else None
    if layout:
        # Every field keeps its place in the grid, an empty one waits for the owner's choice.
        felder = LAYOUTS[layout]
        blocks = [clean_block(x) or dict(EMPTY) for x in _list(raw.get("blocks"))[:felder]]
        blocks += [dict(EMPTY) for _ in range(felder - len(blocks))]
    else:
        blocks = [b for b in (clean_block(x) for x in _list(raw.get("blocks")))
                  if b and b["kind"] != "empty"][:PAGES_MAX_BLOCKS]
    out = {"id": sid, "title": _short(raw.get("title")),
           "lead": text(raw.get("lead"), PAGES_MAX_LONG_CHARS), "blocks": blocks}
    if layout:
        out["layout"] = layout
    if raw.get("hero"):
        out["hero"] = True
        out["meta"] = text(raw.get("meta"), PAGES_MAX_LONG_CHARS)
        # The title block carries its picture and nothing else.
        out["blocks"] = [b for b in blocks if b["kind"] == "image"][:1]
    if raw.get("hidden"):
        out["hidden"] = True
    if not out["title"] and not out["lead"] and not any(b["kind"] != "empty" for b in out["blocks"]):
        return None
    taken.add(sid)
    return out


def clean_page(raw) -> dict:
    """The whole page cut to its limits, raises ValueError when it is no page at all."""
    if not isinstance(raw, dict) or not isinstance(raw.get("sections"), list):
        raise ValueError("no page")
    taken: set[str] = set()
    sections = []
    for i, s in enumerate(raw["sections"][:PAGES_MAX_SECTIONS]):
        cleaned = _section(s, taken, i)
        if cleaned:
            sections.append(cleaned)
    # Pictures beyond the limit drop out from the end of the page.
    seen = 0
    for s in sections:
        kept = []
        for b in s["blocks"]:
            if b["kind"] == "image":
                seen += 1
                if seen > PAGES_MAX_IMAGES:
                    continue
            kept.append(b)
        s["blocks"] = kept
    lang = raw.get("lang") if raw.get("lang") in LANGS else "de"
    design = raw.get("design") if raw.get("design") in DESIGNS else DESIGNS[0]
    out = {"version": VERSION, "lang": lang, "design": design, "sections": sections,
           "footer": text(raw.get("footer"), PAGES_MAX_LONG_CHARS)}
    return out


def title_of(page: dict) -> str:
    """The page's own heading, the title block first."""
    for s in page.get("sections") or []:
        if s.get("hero") and s.get("title"):
            return s["title"]
    for s in page.get("sections") or []:
        if s.get("title"):
            return s["title"]
    return ""


def first_image(page: dict) -> str:
    """The first picture of the page, shown on its card, "" when it has none."""
    for s in page.get("sections") or []:
        if s.get("hidden"):
            continue
        for b in s.get("blocks") or []:
            if b.get("kind") == "image":
                return b.get("src") or ""
    return ""


def for_viewers(page: dict) -> dict:
    """The page as others see it, hidden sections never leave the server."""
    return {**page, "sections": [s for s in page.get("sections") or [] if not s.get("hidden")]}


def images_of(page: dict) -> set[str]:
    """Every picture the page shows, the shared view serves only these."""
    return {b["src"] for s in for_viewers(page)["sections"] for b in s.get("blocks") or []
            if b.get("kind") == "image" and b.get("src")}
