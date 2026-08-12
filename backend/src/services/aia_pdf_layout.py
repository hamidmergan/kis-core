"""Layout-aware reading of a PDF page: reading order, boilerplate, slide grouping.

Why this exists: a slide page used to enter the index as ONE chunk holding the whole
slide, running header and footer included. Its embedding is then the average of
everything on the page, so the one bullet a reader is actually after ("10 Minuten
Fragerunde/Diskussion") barely registers. Measured against a real course recording,
that page sat at cosine distance 0.513 from the sentence it backs, while three
transcript segments that merely TALK about the same thing sat at 0.325-0.510 and took
every citation slot. The same page cut down to its own bullet group sits at 0.205, i.e.
ahead of the video.

Everything here works off geometry and repetition, never off words, so it holds for
every language a course ships in.
"""

import re
from dataclasses import dataclass

# A page's own line is boilerplate when it stands on at least this share of pages.
# Below it a repeat is a coincidence (two chapters opening with the same heading).
_BOILERPLATE_SHARE = 0.6
# Under this many pages "stands on most pages" says nothing at all.
_BOILERPLATE_MIN_PAGES = 4
# A bare number on its own line is a page number wherever it sits. Length-capped so a
# year or a figure in its own text box is not mistaken for one.
_PAGE_NUMBER_MAX_DIGITS = 4
# Two lines belong to the same visual row when their baselines differ by less than
# this (points). Columns of one row come back with slightly different baselines.
_ROW_TOLERANCE = 1.0
# A sub-bullet is indented by at least this much (points) relative to the level above.
# Well under the ~36pt step PowerPoint uses, well above baseline jitter.
_INDENT_STEP = 12.0

_BULLET_MARKS = ("•", "▪", "‣", "◦", "·", "-", "–", "—", "*")
# A page counts as a list only when this share of its lines are bullets. Prose pages carry
# the odd dash and must not be cut along it.
_BULLET_SHARE_MIN = 0.5
# A heading is short. These caps keep body text from being copied into every group of its
# page, which is how one statute page grew from 3050 to 7157 characters.
_TITLE_LINE_MAX_CHARS = 80
_TITLE_MAX_CHARS = 120


@dataclass(frozen=True)
class LineBox:
    """One extracted line with the geometry pdfium reports for it.

    ``x`` is the left edge, ``y`` the top edge in PDF units (origin bottom-left, so a
    LARGER y is FURTHER UP the page).
    """

    text: str
    x: float
    y: float


def page_reading_order(lines: list[LineBox]) -> list[LineBox]:
    """The page's lines as a reader meets them: top to bottom, then left to right.

    Extraction order is object order, which on a slide deck puts the title LAST (its
    text box was authored after the body). Sorting by falling y puts the title back on
    top, where it belongs both for a human and for the group prefix below.
    """
    return sorted(lines, key=lambda b: (-round(b.y / _ROW_TOLERANCE), b.x))


def _norm(text: str) -> str:
    """Comparison form of a line: letters and digits only, lowercased, single-spaced.

    Punctuation is dropped because the SAME footer reaches us in three spellings: the
    plain text run separates the parts with " - ", assembling rows joins them with a
    space, and on an image-heavy page the OCR model re-transcribes it in its own
    punctuation. Counted separately, none of the three stands on enough pages to look
    like furniture; counted as one, all of them do.
    """
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _is_page_number(text: str) -> bool:
    s = text.strip()
    return s.isdigit() and len(s) <= _PAGE_NUMBER_MAX_DIGITS


def merge_rows(boxes: list[LineBox]) -> list[LineBox]:
    """Join text rects that belong to one line into a single line.

    Two joins happen here. Rects on the SAME baseline are one line (a bold word inside a
    sentence comes back as its own rect). And a rect holding nothing but a bullet glyph
    belongs to the text rect that follows it: pdfium reports the two separately and NOT
    on the same baseline — measured on a real deck the glyph sits 7.8pt above its own
    words, further apart than some decks set their line spacing — so a baseline band
    cannot join them without also gluing neighbouring lines together. The merged line
    keeps the GLYPH's left edge, which is what carries the indent level.
    """
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


# A repeating fragment shorter than this is never furniture. Bullet glyphs come back as
# their own text objects and stand on nearly every page of a deck, so without this floor
# "•" would be classified as a running header and the page would lose its structure.
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
    """Comparison forms of the lines that are running furniture in this document.

    A line that stands on most pages carries no information about the page it is on,
    but it does drag every one of those pages' embeddings towards itself. Counted per
    PAGE, never matched against known header words, so it holds in any language.

    Both representations of the SAME page are counted, because both get filtered later
    and they do not agree. The footer of a real deck is three text objects
    ("Wissenschaftliches Seminar", "Einführung", "Lenka Kleinau, M.Sc.") that pdfium's
    plain text run glues into one line. Counting only the geometry pieces produced keys
    that never matched the glued line, so the footer rode along in 19 of 32 chunks of
    that document — removed from the slide pages, kept on every other page.
    """
    keys = _repeated_keys([[b.text for b in page] for page in pages])
    if page_texts is not None:
        keys |= _repeated_keys([t.splitlines() for t in page_texts])
    return keys


def is_boilerplate(text: str, keys: set[str]) -> bool:
    """True for a running header/footer line or a bare page number."""
    return _norm(text) in keys or _is_page_number(text)


def strip_boilerplate_text(text: str, keys: set[str]) -> str:
    """Remove furniture lines from a page's PLAIN text, order untouched.

    Used for pages that keep the ordinary whole-page path (prose, tables, scans): they
    must not be re-ordered by geometry — a two-column statute would interleave — but
    they should still lose the running header and the page number. Never returns an
    empty page: a page that is nothing but furniture keeps what it had.
    """
    lines = text.splitlines()
    kept = [ln for ln in lines if not is_boilerplate(ln, keys)]
    return "\n".join(kept).strip() or text


def drop_boilerplate_lines(pages: list[list[LineBox]]) -> list[list[LineBox]]:
    """Remove the running header/footer from every page of a document.

    A line that stands on most pages carries no information about the page it is on,
    but it does drag every one of those pages' embeddings towards itself. Detected by
    counting how many PAGES a line appears on, never by matching known header words.
    Page numbers are covered separately: they differ on every page yet are the same
    furniture.

    A page is never emptied completely — a page whose every line looks like furniture
    keeps what it has, because a blank page cannot be cited at all.
    """
    boiler = boilerplate_keys(pages)
    if not boiler and len(pages) < _BOILERPLATE_MIN_PAGES:
        return pages
    out: list[list[LineBox]] = []
    for page in pages:
        kept = [b for b in page if not is_boilerplate(b.text, boiler)]
        out.append(kept or page)
    return out


def _bullet_level(box: LineBox, lefts: list[float]) -> int:
    """Indent level of a bullet line, 0 for the leftmost column on the page.

    Levels come from the DISTINCT left edges of the page's bullet lines, so a deck that
    indents by 20pt and one that indents by 40pt are read the same way.
    """
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
    """Cut a bullet-structured page into one text per TOP-LEVEL bullet group.

    Each group is the top-level bullet plus everything indented under it, prefixed with
    the page's title lines so the group still says where it belongs. Neighbouring groups
    too thin to stand on their own (< ``min_chars``) are folded together. Size is NOT
    this function's business: the caller runs every group through the same length
    splitter it uses for any other page text.

    Returns ``[]`` when there is nothing to gain — prose, a table, a single bullet, or a
    page whose groups all fold back into one. The caller then keeps the whole-page path.
    """
    ordered = page_reading_order(lines)
    bullets = [b for b in ordered if _is_bullet(b.text)]
    if len(bullets) < 2:
        return []
    # A page is only cut when it really IS a list. A statute page carrying a long
    # paragraph plus a handful of dashed citation notes is prose that happens to contain
    # dashes; cutting one turned 3050 characters into 7157, because the paragraph rode
    # along in every group. On a slide the bullets ARE the page.
    if len(bullets) < len(ordered) * _BULLET_SHARE_MIN:
        return []
    lefts = sorted({round(b.x, 1) for b in bullets})
    base = lefts[0]
    # The heading that rides on every group has to be a heading: short lines, and few of
    # them. Anything longer is body text and belongs to its own group only.
    above = [b.text.strip() for b in ordered
             if not _is_bullet(b.text) and b.y > bullets[0].y]
    head = [t for t in above if len(t) <= _TITLE_LINE_MAX_CHARS]
    title = " ".join(head)[:_TITLE_MAX_CHARS].strip()
    # What was too long to be a heading is body text and belongs to the FIRST group, the
    # one it leads into. It must land somewhere: dropping it cost a quarter of one deck's
    # text before this line existed.
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

    # NO group may end up under the floor: cutting a page finer must never seed the index
    # with scraps too small to mean anything, which is the very thing that makes a chunk a
    # magnet in vector search. Measured on the FINISHED text, title included, because that
    # is what lands in the index and what every downstream length rule sees — measuring
    # the bullets alone let a group through at 98 characters, just under the 100 at which
    # the citation attribution writes a chunk off as boilerplate.
    #
    # A thin group folds into its predecessor, i.e. the bullet it most likely belongs
    # under; the first group has none and folds forward instead. Milder rules were tried
    # and both failed on real slides: "only fold when BOTH neighbours are thin" stranded a
    # 29-character scrap next to a full group, and "fold the thin tail back" swallowed the
    # 123-character "Präsentationsvorgaben" group, which is short because slide bullets are
    # terse, not because it says little — the very case this module exists for.
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
