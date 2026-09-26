"""Reads a PDF page by its layout: reading order, headers, slide groups."""

import re
from dataclasses import dataclass

from loguru import logger

# From this page share on a line counts as a header or footer.
_BOILERPLATE_SHARE = 0.6
# Under this many pages "stands on most pages" says nothing at all.
_BOILERPLATE_MIN_PAGES = 4
# This close two baselines have to be to be the same line.
_ROW_TOLERANCE = 1.0
# This far a sub-point has to be indented at least.
_INDENT_STEP = 12.0

_BULLET_MARKS = ("•", "▪", "‣", "◦", "·", "-", "–", "—", "*")
# From this share of bullet lines on a page counts as a list.
_BULLET_SHARE_MIN = 0.5
# A heading is short, otherwise prose would land in every group.
_TITLE_LINE_MAX_CHARS = 80
_TITLE_MAX_CHARS = 120


@dataclass(frozen=True)
class LineBox:
    """One line with the position pdfium reports for it."""

    text: str
    x: float
    y: float


def page_reading_order(lines: list[LineBox]) -> list[LineBox]:
    """The lines of the page in reading order, top to bottom."""
    return sorted(lines, key=lambda b: (-round(b.y / _ROW_TOLERANCE), b.x))


# A page counter: "Seite 3 von 12", "Page 3 of 12", "Folie 3", "S. 3", "3 / 12" or a bare "3".
_COUNTER = r"(?:(?:seite|page|folie|slide|s\.|p\.)\s*)?\d{1,4}(?:\s*(?:von|of|/)\s*\d{1,4})?"
# The counter with its total, specific enough to stand at a line's edge without a separator.
_FULL_COUNTER = r"(?:(?:seite|page|folie|slide)\s*)?\d{1,4}\s*(?:von|of|/)\s*\d{1,4}"
_SEPARATOR = r"[|•·–—-]"
# The counter at either end of a running title, so the title is the same line on every page.
_EDGE_COUNTER = re.compile(
    rf"^\s*{_COUNTER}\s*{_SEPARATOR}|{_SEPARATOR}\s*{_COUNTER}\s*$"
    rf"|^\s*{_FULL_COUNTER}\b|\b{_FULL_COUNTER}\s*$", re.I)
# A line that is nothing but a counter, "Seite 3 von 12" or "- 3 -".
_PAGE_NUMBER = re.compile(rf"^[\s|•·–—-]*{_COUNTER}[\s|•·–—-]*$", re.I)


def _norm(text: str) -> str:
    """Comparison form of a line: letters and digits only, a page counter at its edge left out.

    Without the counter, a footer that differs only in its page number is the same line
    on every page.
    """
    ohne = _EDGE_COUNTER.sub(" ", text)
    return " ".join(re.sub(r"[^\w\s]", " ", ohne.lower()).split())


def _is_page_number(text: str) -> bool:
    """A line that is nothing but a page counter."""
    return bool(_PAGE_NUMBER.match(text.strip()))


def merge_rows(boxes: list[LineBox]) -> list[LineBox]:
    """Joins the text boxes of a line, including a leading bullet."""
    rows: dict[int, list[LineBox]] = {}
    for b in boxes:
        rows.setdefault(round(b.y / _ROW_TOLERANCE), []).append(b)
    lines: list[LineBox] = []
    for key in sorted(rows, reverse=True):
        parts = sorted(rows[key], key=lambda b: b.x)
        text = " ".join(p.text.strip() for p in parts if p.text.strip())
        if text:
            lines.append(LineBox(text=text, x=parts[0].x, y=parts[0].y))

    out: list[LineBox] = []
    pending: LineBox | None = None
    for line in lines:
        if _is_lone_bullet(line.text):
            pending = line
            continue
        if pending is not None:
            line = LineBox(text=f"{pending.text.strip()} {line.text}", x=pending.x, y=pending.y)
            pending = None
        out.append(line)
    if pending is not None:      # a glyph with nothing after it: keep, never drop text
        out.append(pending)
    return out


def _is_lone_bullet(text: str) -> bool:
    s = text.strip()
    return len(s) == 1 and s in _BULLET_MARKS


# A recurring piece that is too short is never a header.
_BOILERPLATE_MIN_CHARS = 4


def _repeated_keys(pages: list[list[str]]) -> set[str]:
    """Comparison forms of the lines standing on at least _BOILERPLATE_SHARE of pages."""
    if len(pages) < _BOILERPLATE_MIN_PAGES:
        return set()
    seen_on: dict[str, set] = {}
    for i, page in enumerate(pages):
        for text in page:
            key = _norm(text)
            if len(key) < _BOILERPLATE_MIN_CHARS:
                continue
            seen_on.setdefault(key, set()).add(i)
    limit = len(pages) * _BOILERPLATE_SHARE
    return {key for key, on in seen_on.items() if len(on) >= limit}


def boilerplate_keys(pages: list[list[LineBox]],
                     page_texts: list[str] | None = None) -> set[str]:
    """The comparison forms of the lines that are header or footer in this document."""
    keys = _repeated_keys([[b.text for b in page] for page in pages])
    if page_texts is not None:
        keys |= _repeated_keys([t.splitlines() for t in page_texts])
    return keys


def is_boilerplate(text: str, keys: set[str]) -> bool:
    """True for a running header/footer line or a bare page number."""
    return _norm(text) in keys or _is_page_number(text)


# This close in height a short leftover sits to a header or footer piece to belong to it.
_FURNITURE_ROW = 3.0


def strip_furniture(boxes: list[LineBox], keys: set[str]) -> list[LineBox]:
    """The boxes of a page without header and footer, their short leftovers included.

    A footer often arrives in pieces, "- Seite", "2", "von", "11", "-". The long pieces are
    recognised, the short ones in between are only dropped when they share a row with a
    piece that repeats through the document and stands above or below all the content of
    the page. A bare number is not enough, in a formula it would take its neighbours along.
    """
    weg = [b for b in boxes if is_boilerplate(b.text, keys)]
    inhalt = [b.y for b in boxes if b not in weg and len(_norm(b.text)) >= _BOILERPLATE_MIN_CHARS]
    rand = [w for w in weg if _norm(w.text) in keys
            and (not inhalt or w.y > max(inhalt) or w.y < min(inhalt))]

    def rest(b: LineBox) -> bool:
        return (len(_norm(b.text)) < _BOILERPLATE_MIN_CHARS
                and any(abs(b.y - w.y) <= _FURNITURE_ROW for w in rand))

    return [b for b in boxes if b not in weg and not rest(b)]


def strip_boilerplate_text(text: str, keys: set[str]) -> str:
    """Removes headers and footers from the page text without changing the order."""
    lines = text.splitlines()
    kept = [ln for ln in lines if not is_boilerplate(ln, keys)]
    return "\n".join(kept).strip() or text


def drop_boilerplate_lines(pages: list[list[LineBox]]) -> list[list[LineBox]]:
    """Removes the header and footer from every page, counted instead of guessed."""
    boiler = boilerplate_keys(pages)
    if not boiler and len(pages) < _BOILERPLATE_MIN_PAGES:
        return pages
    out: list[list[LineBox]] = []
    for page in pages:
        kept = [b for b in page if not is_boilerplate(b.text, boiler)]
        out.append(kept or page)
    return out


def _bullet_level(box: LineBox, lefts: list[float]) -> int:
    """Indent level of a bullet line, 0 for the left column."""
    level = 0
    for edge in lefts:
        if box.x >= edge + _INDENT_STEP:
            level += 1
    return level


def _is_bullet(text: str) -> bool:
    s = text.lstrip()
    return bool(s) and s[0] in _BULLET_MARKS


def _strip_mark(text: str) -> str:
    s = text.lstrip()
    return s[1:].strip() if s and s[0] in _BULLET_MARKS else s.strip()


def slide_groups(lines: list[LineBox], *, min_chars: int) -> list[str]:
    """Cuts a bullet page into one text per main point."""
    ordered = page_reading_order(lines)
    bullets = [b for b in ordered if _is_bullet(b.text)]
    if len(bullets) < 2:
        return []
    # Cutting only happens where the page really is a list.
    if len(bullets) < len(ordered) * _BULLET_SHARE_MIN:
        return []
    lefts = sorted({round(b.x, 1) for b in bullets})
    base = lefts[0]
    # Whatever travels with every group has to be a heading.
    above = [b.text.strip() for b in ordered
             if not _is_bullet(b.text) and b.y > bullets[0].y]
    head = [t for t in above if len(t) <= _TITLE_LINE_MAX_CHARS]
    title = " ".join(head)[:_TITLE_MAX_CHARS].strip()
    # Text that is too long is prose and belongs to the first group.
    lead = [t for t in above if len(t) > _TITLE_LINE_MAX_CHARS]

    groups: list[list[str]] = []
    for box in ordered:
        if not _is_bullet(box.text):
            if groups:                       # wrapped continuation under a bullet
                groups[-1].append(box.text.strip())
            continue
        text = _strip_mark(box.text)
        if _bullet_level(box, [base]) == 0 or not groups:
            groups.append([text])
        else:
            groups[-1].append(text)
    if len(groups) < 2:
        return []
    if lead:
        groups[0] = lead + groups[0]

    def render(parts: list[str]) -> str:
        body = "\n".join(f"• {p}" for p in parts)
        return f"{title}\n{body}" if title else body

    # No group may fall below the minimum length, thin ones fold together.
    merged: list[list[str]] = [list(g) for g in groups]

    def fold_one() -> bool:
        for i, g in enumerate(merged):
            if len(render(g)) >= min_chars or len(merged) < 2:
                continue
            other = i - 1 if i > 0 else i + 1
            lo, hi = min(i, other), max(i, other)
            merged[lo] = merged[lo] + merged[hi]
            merged.pop(hi)
            return True
        return False

    while fold_one():
        pass

    return [render(p) for p in merged] if len(merged) >= 2 else []


def line_boxes(textpage) -> list[LineBox]:
    """The raw text boxes of a pdfium page with their position, empty is a valid answer."""
    from src.services.text_pieces import clean
    try:
        n = textpage.count_rects()
    except Exception as e:  # noqa: BLE001 - without boxes the plain page text still works
        logger.warning("PDF-Layout: Kaesten nicht zaehlbar, es geht ohne ({})", e)
        return []
    boxes: list[LineBox] = []
    for i in range(n):
        try:
            left, top, right, bottom = textpage.get_rect(i)
            text = textpage.get_text_bounded(left=left, bottom=bottom, right=right, top=top)
        except Exception:  # noqa: BLE001 - one unreadable box is not worth the page
            continue
        text = clean(text or "").strip()
        if text:
            boxes.append(LineBox(text=text, x=left, y=top))
    return boxes
