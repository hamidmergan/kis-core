"""Compute exact character-offset spans for PDF citation highlights (Architecture B).

The highlight bounds are computed ONCE, server-side, on the page's pdfium text —
the SAME text the EmbedPDF viewer loads (both use pdfium on the same file), so the
character offsets line up. The chip then carries ``@start-end`` plus the verbatim
span text, and the viewer draws that precise sentence without guessing
sentence/paragraph bounds.

Language-agnostic by construction: only punctuation, whitespace and Unicode case
drive the logic — no wordlists, so it works for every tenant/PDF language.
"""
from __future__ import annotations

import os
import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_BRACKETS_RE = re.compile(r"[\[\]【】|❘]")
_MAX_SPAN_CHARS = 220          # never highlight more than ~one long sentence
_MIN_CORE_CHARS = 6            # shorter verbatim overlaps are too weak to anchor on
_MEDIA_EXTS = {"mp3", "mp4", "wav", "flac", "m4a", "webm"}


def _fold_char(ch: str) -> str:
    """Diacritic-fold a single char to its NFKD base, lowercased. One char in →
    one char out, so indices stay aligned. Mirrors the frontend _foldDiacritics."""
    d = unicodedata.normalize("NFKD", ch)
    return (d[0] if d else ch).lower()


def _collapse_fold(text: str) -> tuple[str, list[int]]:
    """Return a whitespace-collapsed, diacritic-folded view of ``text`` plus a map
    from each clean-index back to the original ``text`` index. A run of whitespace
    becomes a single space mapped to the run's first char. Mirrors the frontend
    collapseFold so both sides match the same way."""
    clean: list[str] = []
    c2t: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not in_space:
                clean.append(" ")
                c2t.append(i)
                in_space = True
        else:
            clean.append(_fold_char(ch))
            c2t.append(i)
            in_space = False
    return "".join(clean), c2t


# ── Page text ───────────────────────────────────────────────────────────────

def _open_pdf(source: dict):
    """Open the source PDF with pypdfium2 from local disk or object storage.
    Returns a PdfDocument or None. Caller must close it."""
    path = source.get("file_path") or ""
    if not path:
        return None
    import pypdfium2 as pdfium
    from src.storage import USE_S3
    if path and not USE_S3 and os.path.exists(path):
        return pdfium.PdfDocument(path)
    from src.storage import get_file
    return pdfium.PdfDocument(get_file(path))


def get_page_text(source: dict, page_number: int, cache: dict | None = None) -> str | None:
    """Return the pdfium text of a PDF page (1-indexed), or None.

    None when: media source, missing file, page out of range, OCR-only/empty page,
    or any extraction error. Results are memoised in ``cache`` (one dict per
    request) keyed by ``(source_id, page_number)``."""
    if not source or page_number is None:
        return None
    ext = (source.get("file_type") or "").lower().lstrip(".")
    if ext in _MEDIA_EXTS:
        return None
    key = (source.get("id"), page_number)
    if cache is not None and key in cache:
        return cache[key]

    text: str | None = None
    try:
        doc = _open_pdf(source)
        if doc is not None:
            try:
                if 0 <= page_number - 1 < len(doc):
                    page = doc[page_number - 1]
                    tp = page.get_textpage()
                    raw = tp.get_text_range() or ""
                    tp.close()
                    page.close()
                    text = raw if raw.strip() else None
            finally:
                doc.close()
    except Exception:
        text = None
    if cache is not None:
        cache[key] = text
    return text


# ── Span location ─────────────────────────────────────────────────────────────

def _is_abbrev_dot(text: str, i: int) -> bool:
    """True if the '.' at index i is an abbreviation/decimal dot, not a sentence end.
    Mirrors the frontend _isAbbrevDot (language-agnostic: punctuation + case only)."""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt and nxt.isalpha():                 # dot glued to a letter: "z.B", "d.h", "U.S.A"
        return True
    if i >= 1 and text[i - 1].isalpha() and (i < 2 or text[i - 2] in " ."):
        return True                            # single-letter initial / multi-dot abbrev: "S." "z.B." "U.S.A."
    if i >= 1 and text[i - 1].isdigit():       # decimal / numbered: "3." "49."
        return True
    return False


def _expand_sentence(text: str, a: int, b: int) -> tuple[int, int]:
    """Expand the inclusive core [a, b] to its sentence/line bounds within ``text``.
    Stops at '\\n', '!', '?', or a non-abbreviation '.'. Whitespace at the edges is
    trimmed back to the core."""
    n = len(text)
    s = 0
    for i in range(a - 1, -1, -1):
        ch = text[i]
        if ch == "\n" or ch in "!?":
            s = i + 1
            break
        if ch == "." and not _is_abbrev_dot(text, i):
            s = i + 1
            break
    e = n - 1
    for j in range(b + 1, n):
        ch = text[j]
        if ch == "\n":
            e = j - 1
            break
        if ch in "!?" or (ch == "." and not _is_abbrev_dot(text, j)):
            e = j
            break
    while s < a and text[s].isspace():
        s += 1
    while e > b and text[e].isspace():
        e -= 1
    return s, e


def locate_claim_span(page_text: str, claim: str) -> tuple[int, int] | None:
    """Locate the claim on the page and return its inclusive sentence span as
    ``(start, end)`` offsets into ``page_text`` — or None when no confident anchor
    exists.

    Strategy: find the longest contiguous run of claim tokens that occurs verbatim
    (whitespace-collapsed, diacritic-folded) on the page, then expand that core to
    its sentence bounds. The whole span is capped at ``_MAX_SPAN_CHARS``."""
    if not page_text or not claim:
        return None
    clean_t, c2t = _collapse_fold(page_text)
    claim_clean = _WS_RE.sub(" ", "".join(_fold_char(c) for c in claim)).strip()
    toks = [t for t in claim_clean.split(" ") if t]
    if not toks:
        return None

    core: tuple[int, int] | None = None
    for size in range(len(toks), 0, -1):
        for i in range(0, len(toks) - size + 1):
            phrase = " ".join(toks[i:i + size])
            if len(phrase) < _MIN_CORE_CHARS:
                continue
            idx = clean_t.find(phrase)
            if idx >= 0:
                core = (idx, idx + len(phrase) - 1)
                break
        if core:
            break
    if core is None:
        return None

    ta, tb = c2t[core[0]], c2t[core[1]]
    start, end = _expand_sentence(page_text, ta, tb)
    if end - start + 1 > _MAX_SPAN_CHARS:
        # Sentence is a wall of text: window it around the matched core instead.
        center = (ta + tb) // 2
        half = _MAX_SPAN_CHARS // 2
        start = max(start, center - half)
        end = min(end, center + half)
        while start < ta and page_text[start].isspace():
            start += 1
        while end > tb and page_text[end].isspace():
            end -= 1
    return (start, end)


def span_text(page_text: str, start: int, end: int) -> str:
    """The verbatim span as a single-line, chip-safe string: whitespace collapsed,
    bracket/pipe chars (which would break the chip syntax) replaced by spaces."""
    raw = page_text[start:end + 1]
    s = _BRACKETS_RE.sub(" ", raw)
    return _WS_RE.sub(" ", s).strip()


def offset_suffix(source: dict, page_number: int, claim: str, cache: dict | None = None) -> str | None:
    """Return ``' @start-end | <span text>'`` for a PDF citation, or None when no
    offsets can be computed (caller keeps its existing keyword / position-only chip)."""
    page = get_page_text(source, page_number, cache)
    if not page:
        return None
    span = locate_claim_span(page, claim)
    if not span:
        return None
    start, end = span
    txt = span_text(page, start, end)
    if len(txt) < _MIN_CORE_CHARS:
        return None
    return f" @{start}-{end} | {txt}"
