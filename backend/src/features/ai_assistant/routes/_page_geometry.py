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
# A URL inside the chip keyword breaks the client's markdown render (gfm autolinks
# it and splits the citation token), so drop it from the displayed span text. The
# highlight itself is driven by the @start-end offsets, not this text, so removing
# the URL costs nothing.
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)   # Unicode letter/digit runs (no '_')
_MAX_SPAN_CHARS = 220          # never highlight more than ~one long sentence
_MIN_CORE_CHARS = 6            # shorter verbatim overlaps are too weak to anchor on
_MEDIA_EXTS = {"mp3", "mp4", "wav", "flac", "m4a", "webm"}

# Multi-region anchoring: besides the primary (longest verbatim) span, also anchor
# OTHER sentences on the SAME page that share enough CONTENT words with the claim, so
# a synthesised answer line ("… ca. 6–7 Seiten inkl. Abbildungen/Tabellen …") marks
# every spot it draws from — not only the strongest verbatim match. Overlap survives
# paraphrase and punctuation drift ('–' vs '-') that breaks the contiguous matcher.
# Pure length/overlap heuristics, no wordlists → language-agnostic for every tenant.
_MIN_TOKEN_LEN = 4          # a "content word"; shorter function words are ignored
_MIN_SECONDARY_TOKENS = 3   # an extra sentence needs >= this many shared content words
_MAX_SPANS = 3              # primary + up to two extra regions per citation


def _fold_char(ch: str) -> str:
    """Diacritic-fold a single char to its NFKD base, lowercased. One char in →
    one char out, so indices stay aligned. Mirrors the frontend _foldDiacritics."""
    d = unicodedata.normalize("NFKD", ch)
    return (d[0] if d else ch).lower()


# Invisible join / OCR line-break artifacts: dropped entirely by the fold so a word
# split across a hyphenated line break ("Bachelor<artifact>Studiengangs", "Kla<shy>ren")
# matches the live pdfium text (which joins it or uses a different separator). Soft
# hyphen, zero-width chars, word joiner, BOM/ZWNBSP, and the U+FFFE/U+FFFF noncharacters
# Docling emits. MUST mirror the frontend _FOLD_SKIP.
_FOLD_SKIP = frozenset("­​‌‍⁠﻿￾￿")


def _collapse_fold(text: str) -> tuple[str, list[int]]:
    """Return a whitespace-collapsed, diacritic-folded view of ``text`` plus a map
    from each clean-index back to the original ``text`` index. A run of whitespace
    becomes a single space mapped to the run's first char. Invisible join/OCR artifacts
    (see _FOLD_SKIP) are dropped so a span survives a hyphenated line break. Mirrors the
    frontend collapseFold so both sides match the same way."""
    clean: list[str] = []
    c2t: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch in _FOLD_SKIP:
            continue
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
    # A real sentence end is continued by an UPPERCASE start. If a SPACE follows the
    # dot and the next non-space char is a digit or a lowercase letter, the dot is an
    # abbreviation / number continuation ("ca. 6-7", "ca. 2 Seiten", "z.B. das"), NOT
    # a sentence boundary. The space requirement keeps glued footnote markers
    # ("erprobt.11") as real ends. Case-based, no wordlist — works for any language.
    if nxt.isspace():
        k = i + 1
        while k < len(text) and text[k].isspace():
            k += 1
        if k < len(text):
            nc = text[k]
            if nc.isdigit() or (nc.isalpha() and nc.islower()):
                return True
    return False


# A line break that opens one of these is a genuine NEW item, not a wrap.
# NB: the middle dot '·' (U+00B7) is deliberately NOT here — in maths PDFs it is
# the multiplication operator ("· 2x"), so treating it as a bullet would cut the
# formula tail off the highlight. Real list bullets use '•' (U+2022) et al.
_LIST_MARKER = re.compile(r"^(?:[•▪◦‣⁃●○…*]|\.{2,}|[-–—]\s|\(?\d{1,3}[.)]\s)")
_DATE_LIKE = re.compile(r"^\d{1,4}[.\-/]\d{1,2}(?:[.\-/]\d{1,4})?\b")


def _line_is_boundary(text: str, j: int) -> bool:
    """True if the '\\n' at index ``j`` is a real sentence/line boundary; False if it
    is only a soft wrap or an inline-formula fragment break that should be bridged.

    pdfium emits superscripts/exponents/primes (x², f′, e^x, ℝ) as their OWN short
    "line" between \\r\\n, so naively stopping at every '\\n' cuts maths symbols off the
    highlight. This mirrors the frontend ``_looksLikeNewBullet`` heuristic — purely
    punctuation / list-marker / Unicode-case / line-length, no wordlists, so it stays
    language-agnostic for every tenant."""
    n = len(text)
    p = j - 1
    while p >= 0 and text[p] in " \t\r":
        p -= 1
    if p < 0:
        return False
    prev_char = text[p]
    ls = p
    while ls > 0 and text[ls - 1] != "\n":
        ls -= 1
    prev_line_len = p - ls + 1
    k = j + 1
    while k < n and text[k] in " \t\r\n":
        k += 1
    if k >= n:
        return False
    after = text[k:k + 60]
    nxt = text[k]
    if prev_char == "-":
        return False                       # hyphenated wrap
    if prev_char in ",;:":
        return False                       # clause / list continues
    if _LIST_MARKER.match(after) or _DATE_LIKE.match(after):
        return True                        # new list/enumeration/date item
    if prev_char in ".!?":
        return True                        # previous sentence ended
    if not nxt.isupper():
        return False                       # lowercase/digit/operator/prime/paren → continuation (wrap or formula)
    # Ambiguous Title-case line after another: a SHORT ended line is a heading /
    # standalone item (boundary); a near-full-width line is wrapped prose (bridge).
    return prev_line_len <= 55


def _expand_sentence(text: str, a: int, b: int) -> tuple[int, int]:
    """Expand the inclusive core [a, b] to its sentence/line bounds within ``text``.
    Stops at '!', '?', a non-abbreviation '.', or a '\\n' that is a real line boundary
    (``_line_is_boundary``) — a '\\n' that only separates an inline maths fragment is
    bridged so superscripts/primes stay in the highlight. Edge whitespace is trimmed."""
    n = len(text)
    s = 0
    for i in range(a - 1, -1, -1):
        ch = text[i]
        if ch == "\n":
            if _line_is_boundary(text, i):
                s = i + 1
                break
            continue
        if ch in "!?" or (ch == "." and not _is_abbrev_dot(text, i)):
            s = i + 1
            break
    e = n - 1
    for j in range(b + 1, n):
        ch = text[j]
        if ch == "\n":
            if _line_is_boundary(text, j):
                e = j - 1
                break
            continue
        if ch in "!?" or (ch == "." and not _is_abbrev_dot(text, j)):
            e = j
            break
    while s < a and text[s].isspace():
        s += 1
    while e > b and text[e].isspace():
        e -= 1
    return s, e


def _content_tokens(text: str) -> set[str]:
    """Folded content words of ``text`` (length >= _MIN_TOKEN_LEN). Diacritic-folded
    and lowercased so they compare equal across umlaut/case drift; no wordlist, so it
    is language-agnostic. Short function words are dropped to keep the overlap signal
    about substance, not glue words."""
    folded = "".join(_fold_char(c) for c in text)
    return {t for t in _TOKEN_RE.findall(folded) if len(t) >= _MIN_TOKEN_LEN}


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


def locate_claim_spans(page_text: str, claim: str, max_spans: int = _MAX_SPANS) -> list[tuple[int, int]]:
    """Locate EVERY region of ``page_text`` the claim draws from, not just the best one.

    Returns inclusive ``(start, end)`` spans, sorted by position:
      1. the primary span (longest verbatim run, via ``locate_claim_span``), if any;
      2. up to ``max_spans - 1`` other sentences that share >= _MIN_SECONDARY_TOKENS
         distinct content words with the claim and don't overlap a kept span.

    So a synthesised line whose pieces live in different bullets on one page gets a
    mark on each. Overlap (not verbatim run) drives 2., so it survives paraphrase and
    '–'/'-' punctuation drift. Language-agnostic: only folding, length and set
    overlap — no wordlists."""
    spans: list[tuple[int, int]] = []
    primary = locate_claim_span(page_text, claim)
    if primary:
        spans.append(primary)
    if not page_text or not claim:
        return spans
    claim_toks = _content_tokens(claim)
    if len(claim_toks) < _MIN_SECONDARY_TOKENS:
        return spans

    clean_t, c2t = _collapse_fold(page_text)
    # Group page content-word hits by the sentence that contains them; track the
    # distinct claim tokens matched and the raw extent of those tokens per sentence.
    hits: dict[tuple[int, int], dict] = {}
    for m in _TOKEN_RE.finditer(clean_t):
        tok = m.group()
        if tok not in claim_toks:
            continue
        ta, tb = c2t[m.start()], c2t[m.end() - 1]
        s, e = _expand_sentence(page_text, ta, tb)
        h = hits.get((s, e))
        if h is None:
            hits[(s, e)] = {"toks": {tok}, "lo": ta, "hi": tb}
        else:
            h["toks"].add(tok)
            h["lo"] = min(h["lo"], ta)
            h["hi"] = max(h["hi"], tb)

    cands: list[tuple[int, int, int]] = []   # (token_count, start, end)
    for (s, e), h in hits.items():
        if len(h["toks"]) < _MIN_SECONDARY_TOKENS:
            continue
        if any(not (e < ps or pe < s) for ps, pe in spans):   # overlaps a kept span
            continue
        cs, ce = s, e
        if ce - cs + 1 > _MAX_SPAN_CHARS:
            # Wall-of-text sentence: window around the matched tokens (as primary does).
            center = (h["lo"] + h["hi"]) // 2
            half = _MAX_SPAN_CHARS // 2
            cs = max(s, center - half)
            ce = min(e, center + half)
            while cs < h["lo"] and page_text[cs].isspace():
                cs += 1
            while ce > h["hi"] and page_text[ce].isspace():
                ce -= 1
        cands.append((len(h["toks"]), cs, ce))

    cands.sort(key=lambda x: (-x[0], x[1]))   # strongest overlap first, then position
    for _, cs, ce in cands[: max(0, max_spans - len(spans))]:
        spans.append((cs, ce))
    spans.sort(key=lambda sp: sp[0])
    return spans


def span_text(page_text: str, start: int, end: int) -> str:
    """The verbatim span as a single-line, chip-safe string: whitespace collapsed,
    bracket/pipe chars (which would break the chip syntax) replaced by spaces."""
    raw = page_text[start:end + 1]
    s = _BRACKETS_RE.sub(" ", raw)
    s = _URL_RE.sub(" ", s)
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


def offset_suffixes(source: dict, page_number: int, claim: str, cache: dict | None = None) -> list[str]:
    """Like ``offset_suffix`` but returns one ``' @start-end | <span>'`` per region the
    claim draws from on the page (see ``locate_claim_spans``) — primary first. Empty
    list when no confident span exists, so the caller keeps its keyword/position chip.
    The caller emits one ``[N, S. p @…|…]`` chip per suffix; adjacent same-page chips
    are then merged into a single multi-region highlight on the client."""
    page = get_page_text(source, page_number, cache)
    if not page:
        return []
    out: list[str] = []
    for start, end in locate_claim_spans(page, claim):
        txt = span_text(page, start, end)
        if len(txt) < _MIN_CORE_CHARS:
            continue
        out.append(f" @{start}-{end} | {txt}")
    return out
