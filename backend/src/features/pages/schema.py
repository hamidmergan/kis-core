"""The page as data: its sections, how much fits on a page and what others may see of it.

The model's answer and every save of the editor pass through the same cleaning, so a page
on disk always has a shape the frontend can draw. The blocks themselves are in ``blocks``.
"""

from __future__ import annotations

from src.features.pages.blocks import (  # noqa: F401 - the old import path of the block rules
    CHART_LABEL_CHARS,
    CHART_TYPES,
    DATE_CHARS,
    FORMULA_SIGN,
    HIGHLIGHT_KEY_CHARS,
    ICONS,
    IMAGE_NAME,
    MAP_LABEL_CHARS,
    MAX_BRANCHES,
    MAX_CYCLE,
    MAX_EXAMPLE_LINES,
    MAX_FIGURES,
    MAX_LEAVES,
    MAX_LEVELS,
    MAX_SERIES,
    MAX_SIDE_ITEMS,
    MAX_WORDS,
    QUADRANTS,
    SECTION_ID,
    TONES,
    _list,
    _short,
    clean_block,
    number,
    text,
)
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
# A section the owner adds is a grid of fields, the key names the grid and the value its field count.
LAYOUTS = {"1": 1, "2": 2, "21": 2, "12": 2, "3": 3, "4": 4, "1-2": 3}
EMPTY = {"kind": "empty"}
# Where an added section shows its title and lead, "none" shows neither. "top" is the default.
HEADINGS = ("top", "left", "right", "bottom", "none")
# The languages a page is written or translated in.
LANGS = ("de", "en")
# The looks a page can take, the frame call picks one, the frontend draws each differently.
DESIGNS = ("chapters", "timeline", "magazine", "guide")


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
        blocks = [b for b in (clean_block(x) for x in _list(raw.get("blocks"))) if b][:PAGES_MAX_BLOCKS]
    out = {"id": sid, "title": _short(raw.get("title")),
           "lead": text(raw.get("lead"), PAGES_MAX_LONG_CHARS), "blocks": blocks}
    if layout:
        out["layout"] = layout
        if raw.get("heading") in HEADINGS and raw["heading"] != "top":
            out["heading"] = raw["heading"]
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
    return {"version": VERSION, "lang": lang, "design": design, "sections": sections,
            "footer": text(raw.get("footer"), PAGES_MAX_LONG_CHARS)}


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
    """The page as others see it, hidden sections and switched off titles never leave the server."""
    return {**page, "sections": [{**s, "title": "", "lead": ""} if s.get("heading") == "none" else s
                                 for s in page.get("sections") or [] if not s.get("hidden")]}


def images_of(page: dict) -> set[str]:
    """Every picture the page shows, the shared view serves only these."""
    return {b["src"] for s in for_viewers(page)["sections"] for b in s.get("blocks") or []
            if b.get("kind") == "image" and b.get("src")}
