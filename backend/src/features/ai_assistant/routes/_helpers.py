"""Shared helpers for KI-Assistent routes."""

import html as _html
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from loguru import logger
from langfuse.decorators import langfuse_context

from src import database as db
from src.i18n import DEFAULT_LOCALE, t
from src.storage import USE_S3

# Smaller models sometimes emit `[N] S. X` or `[N] MM:SS` (closing the bracket
# before the position label). Repair to `[N, S. X]` / `[N, MM:SS]` so the chip
# parser renders them as clickable citations.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")
_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations into the chip-renderable `[N, pos]` form."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    return text


def _trace_llm(llm, name: str) -> None:
    """Update current Langfuse observation with provider metadata."""
    langfuse_context.update_current_observation(
        metadata={"provider": llm._provider, "base_url": llm._base_url, "model": llm._model},
        name=name,
    )

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (audio/video can be large)

def _convert_office_to_pdf(data: bytes, ext: str, locale: str = DEFAULT_LOCALE) -> bytes:
    """Convert .docx or .pptx to PDF using LibreOffice. Raises HTTPException on failure."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / f"input{ext}"
        src.write_bytes(data)
        result = subprocess.run(
            ["libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", str(tmp), str(src)],
            capture_output=True, text=True, timeout=180,
        )
        pdf_path = tmp / "input.pdf"
        if not pdf_path.exists():
            logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
            raise HTTPException(status_code=500, detail=t("ai.source.pdfConversionFailed", locale))
        return pdf_path.read_bytes()

def _mp4_faststart(data: bytes) -> bytes:
    """Remux MP4 so the moov atom sits at the file start (progressive playback).

    Without this, browsers must download to near end-of-file before playback
    starts - painful for multi-hour recordings. ffmpeg -c copy avoids re-encoding.
    Falls back to the original bytes on any failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / "input.mp4"
        dst = tmp / "output.mp4"
        src.write_bytes(data)
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                 "-c", "copy", "-movflags", "+faststart", str(dst)],
                capture_output=True, text=True, timeout=600,
            )
        except Exception as e:
            logger.warning("KI Tutor: faststart remux exception: {}", e)
            return data
        if result.returncode != 0 or not dst.exists():
            logger.warning("KI Tutor: faststart remux failed (rc={}): {}", result.returncode, result.stderr[:200])
            return data
        return dst.read_bytes()


def _count_pages(ext: str, data: bytes) -> int | None:
    """Return page/slide count for PDF/PPTX, None for formats without a meaningful page count."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(data)
            count = len(doc)
            doc.close()
            return count
        if ext == ".pptx":
            import io
            from pptx import Presentation
            return len(Presentation(io.BytesIO(data)).slides)
    except Exception as e:
        logger.warning("KI Tutor: page count failed for {}: {}", ext, e)
    return None

def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for citation references."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


_TRANSCRIPT_LINE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)"
)


def _parse_ts(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


def _norm_for_match(s: str) -> str:
    """Normalize text for verbatim keyword matching: NFKC, case-fold, unify the
    various Unicode hyphens (e.g. non-breaking U+2011 in 'Peer‑Review'), collapse
    whitespace. Makes the keyword-in-chunk check robust to cosmetic differences."""
    s = unicodedata.normalize("NFKC", s).casefold()
    for hy in ("‐", "‑", "‒", "–", "—", "−"):
        s = s.replace(hy, "-")
    return re.sub(r"\s+", " ", s).strip()


_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    """Drop HTML tags and decode entities, keeping only the visible text.

    docling renders structured pages (tables, headers) as HTML inside the chunk
    text — ``<div data-label="Table">…<td><b>29.05.2026</b></td>…``. Left in, that
    markup leaks into citation keywords and the highlight anchors on tag soup. We
    keep the tags' TEXT content (the real cell values) and discard the tags. The
    tag regex itself is language-agnostic."""
    if not s or "<" not in s:
        return s
    s = _HTML_TAG.sub(" ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


# A table-of-contents / index / list-of-figures entry: a dotted leader run (4+ dots,
# solid OR spaced — "........ 4" and ". . . . 4" — so a normal 3-dot ellipsis is NOT
# caught) followed by a page-reference number. Such a line carries the topic keyword
# verbatim ("Vektorgrafik ........ 4"), so a claim about that topic would wrongly ground
# to the index page instead of the real content section. A letter or digit between the
# dots breaks the run, so abbreviations ("z.B.") and decimals ("3.14") are safe.
# Structure-only -> language-agnostic (KIS is multi-tenant). Limitation: pure whitespace
# alignment with no dots isn't caught (too ambiguous vs. a sentence ending in a number).
_TOC_LEADER_RE = re.compile(r"(?:\.\s*){4,}\d{1,4}")


def _strip_toc_lines(text: str) -> str:
    """Drop lines that are table-of-contents / index entries (dotted leader + page
    number). Works per line, so genuine prose on the same chunk is preserved; a chunk
    that is ENTIRELY such entries collapses to '' and then matches nothing (intended —
    the index page is never the right citation target)."""
    if not text or "." not in text:
        return text
    return "\n".join(ln for ln in text.split("\n") if not _TOC_LEADER_RE.search(ln))


def _is_toc_chunk(content: str, *, min_chars: int = 20, max_kept_ratio: float = 0.4) -> bool:
    """True if a chunk is (almost) entirely table-of-contents / index entries — so it is
    NOT a valid citation target. Measured structurally: if stripping the TOC leader lines
    removes most of the chunk's characters, the chunk WAS a TOC. Prose loses ~nothing.
    Tiny chunks are never flagged (too little signal)."""
    raw = (content or "").replace(" ", "").replace("\n", "")
    if len(raw) < min_chars:
        return False
    kept = _strip_toc_lines(content).replace(" ", "").replace("\n", "")
    return len(kept) <= len(raw) * max_kept_ratio


# Repetition-loop safety net. A model can degenerate into emitting the same few
# lines forever ("fasse detailliert zusammen" on a thin source). We key lines by
# their PROSE only (citations + bullet/heading markers stripped, normalized), so the
# same point with a different chip still counts as a repeat. Substantial lines only —
# short/structural lines (markers, table seps) never trip the guard.
_DEDUP_BRACKET_RE = re.compile(r"[\[【][^\]】]*[\]】]")
_DEDUP_MIN_KEY_LEN = 16


def _line_dedup_key(line: str) -> str:
    """Normalized prose key for a line: strip citation chips + leading list/heading
    markers, then NFKC/casefold/whitespace-normalize. Same key == same content line."""
    s = _DEDUP_BRACKET_RE.sub("", line)
    s = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", s)
    return _norm_for_match(s)


class _RepetitionGuard:
    """Detects a model repetition loop in a streamed answer: a substantial line
    emitted ``max_repeats`` times (consecutive OR alternating). Per-stream state; the
    caller stops consuming the LLM stream the moment ``is_loop`` returns True."""

    def __init__(self, max_repeats: int = 4, min_key_len: int = _DEDUP_MIN_KEY_LEN) -> None:
        self._counts: dict = {}
        self._max = max_repeats
        self._min = min_key_len

    def is_loop(self, line: str) -> bool:
        key = _line_dedup_key(line)
        if len(key) < self._min:
            return False
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] >= self._max


def _tail_repeats(buf: str, *, min_unit: int = 6, max_unit: int = 160,
                  repeats: int = 5, window: int = 2000) -> bool:
    """True when the END of ``buf`` is a short unit repeated back-to-back ``repeats``+
    times — an INTRA-line degeneration loop (a phrase echoed with NO newline).

    The line-based :class:`_RepetitionGuard` never catches this: no line ever completes
    so it is never asked. Observed in GENERIC over 100+ sources, where the model looped
    ``"… (BEG, BStrMKnotV), "`` thousands of times into a single 168k-char / ~11-min
    answer. The stream loop calls this on the GROWING buffer so the runaway is cut early.
    Only the trailing ``window`` chars are scanned, so it is cheap to call periodically.
    ``repeats=5`` of a ``>=6``-char unit keeps it well clear of legitimate prose."""
    tail = buf[-window:]
    n = len(tail)
    for unit in range(min_unit, max_unit + 1):
        if unit * repeats > n:
            break
        seg = tail[-unit:]
        if seg.strip() and tail.endswith(seg * repeats):
            return True
    return False


# Collapse a short unit repeated 3+ times IN A ROW to one occurrence — cleans the
# residue an intra-line loop leaves in the final answer before the stream guard trips.
_COLLAPSE_REPEAT_RE = re.compile(r"(.{6,160}?)(?:\1){3,}", re.DOTALL)


def _collapse_repeats(text: str) -> str:
    """Collapse a unit repeated 3+ times back-to-back to a single copy. Bounded scan;
    skipped on very large input to avoid pathological backtracking cost."""
    if len(text) > 60000:
        return text
    return _COLLAPSE_REPEAT_RE.sub(lambda m: m.group(1), text)


def _dedup_repeated_lines(text: str) -> str:
    """Drop later duplicates of a substantial line (same :func:`_line_dedup_key`).
    Cleans up a repetition loop's residue; blank/short/marker lines pass through."""
    seen: set = set()
    out: list[str] = []
    for line in text.split("\n"):
        key = _line_dedup_key(line)
        if len(key) >= _DEDUP_MIN_KEY_LEN:
            if key in seen:
                continue
            seen.add(key)
        out.append(line)
    return "\n".join(out)


# ── Post-hoc semantic attribution for GENERIC answers ───────────────────────
# Overview answers are where the model's own page citations go wrong (it grounds on
# a frequent word, not meaning). Instead we re-ground each answer line with the SAME
# semantic search that grounds specific questions perfectly: embed the line, search
# the active sources, attach the closest chunk's citation — but ONLY when it is close
# enough. A line that isn't clearly supported gets NO chip (no post-rationalization).
# The distance gate is the make-or-break knob; calibrate at the UI.
_GENERIC_ATTRIB_MAX_DIST = 0.6
# For an answer that IS grounded (>=1 substantial line lands within the normal gate
# above), every OTHER substantial line still gets a chip to its closest retrieved chunk
# up to this looser ceiling — a claim built from the sent chunks must never be left
# without a "where does this come from" link (navigation beats pinpoint precision).
# Beyond this the line is an outlier (or the answer is the honest "not in the sources"
# response, which never grounds <=0.6 and so stays uncited). Tuned above the honest
# distance band observed against off-topic retrieved chunks.
_GUARANTEE_MAX_DIST = 0.85
_MAX_CHIPS_PER_LINE = 3
# An ADDITIONAL chip (multi-chip) is only added when its chunk sits CLOSE to the block's
# best chunk — within this distance delta. A relative gate, not just the absolute 0.6:
# otherwise a clearly-best source (e.g. 0.21) collects spurious near-misses (0.32) that
# are on-topic enough to pass 0.6 but are not where the claim actually came from. Genuine
# co-sources (a fact stated on two pages / in two laws) sit at ~equal distance and stay.
_MULTI_CHIP_MAX_DELTA = 0.08


def _is_seen(chunk: dict, seen_pages_by_source: Optional[dict]) -> bool:
    """True if this chunk's source/page was actually retrieved into the model's context.

    ``None`` mapping == no cross-check (accept). A PDF chunk passes only if its page is in
    the retrieved set for its source; a MEDIA chunk (audio/video — identified by a
    ``start_time``; it ALSO carries a transcript ``page_number`` that is a segment index,
    NOT a navigable page) passes whenever its source was retrieved at all — media is tracked
    by source and navigated by timestamp, so its seen-set is intentionally empty. This is
    what keeps a chip pointing at a page the model never saw."""
    if seen_pages_by_source is None:
        return True
    pages = seen_pages_by_source.get(chunk.get("source_id"))
    if pages is None:
        return False
    if chunk.get("start_time") is not None:   # media: source-level cross-check (no page)
        return True
    pg = chunk.get("page_number")
    return pg is None or pg in pages


def _pick_attribution(hits: list[dict], max_distance: float,
                      seen_pages_by_source: Optional[dict] = None) -> Optional[dict]:
    """Return the closest hit (min cosine ``vec_distance``) iff within the gate, else
    None. None == the line is not clearly in the sources -> no chip is attached.

    When ``seen_pages_by_source`` is given, candidates are FILTERED to pages actually
    retrieved into context BEFORE the closest is chosen — so a line whose globally-closest
    chunk sits on a page that was NOT retrieved (e.g. a non-dominant source only got its
    budget floor) still gets a chip via the closest chunk that WAS retrieved, instead of
    being dropped. The same fact usually appears on several pages; this picks the one the
    model actually saw.

    A table-of-contents / index chunk is never a target: it carries every topic keyword
    verbatim, so it can rank close, but citing the index page is always wrong."""
    cand = [h for h in hits
            if h.get("vec_distance") is not None
            and not _is_toc_chunk(h.get("content") or "")
            and _is_seen(h, seen_pages_by_source)]
    if not cand:
        return None
    best = min(cand, key=lambda h: h["vec_distance"])
    return best if best["vec_distance"] <= max_distance else None


# DE+EN filler — dropped before exact-match so only content words must line up.
_ATTR_STOP = frozenset((
    "der die das ein eine und oder ist hat war wer was wie wo mit von für auf aus bei "
    "den dem des als nach über vor bis wenn dass aber auch noch nur doch sehr wird sind "
    "kann mehr nicht sich gibt diese einer einem einen welche welcher welches dieser "
    "sein ihre über unter zwischen werden wurde "
    "the and or of is in to was that this for with on at by from as it be are were has "
    "had have not but so if then do does did what which who when where why how their "
    "there here than them they you are our its".split()
))
# Keep word chars + German umlauts; allow @ . - inside so emails/hyphenated names and
# numbers survive as one token.
_TOKEN_RE = re.compile(r"[0-9A-Za-zÄÖÜäöüß][0-9A-Za-zÄÖÜäöüß@.\-]*")


def _significant_tokens(line: str) -> list[str]:
    """Distinctive content tokens of a line (lowercased): markdown stripped, words ≥4
    chars that are not stopwords. Proper names, emails and numbers survive; filler is
    dropped. Used to ground a line by VERBATIM presence in a retrieved chunk."""
    s = re.sub(r"[*_`~#>]+", " ", line)
    out: list[str] = []
    for w in _TOKEN_RE.findall(s):
        wl = w.strip(".-").lower()
        if len(wl) >= 4 and wl not in _ATTR_STOP:
            out.append(wl)
    return out


def _exact_attribution_chunk(line: str, context_chunks: list[dict]) -> Optional[dict]:
    """Ground a line by VERBATIM presence in an already-retrieved chunk.

    If every significant token of the line appears (case-insensitive) in one of the
    chunks we already sent to the model, that chunk IS the source — no re-embedding,
    no re-search. This is reliable exactly where semantic attribution fails: a proper
    name / email / number embeds far from its surrounding prose (the same reason an
    author can sit at fused rank ~59), but it is *literally* present in the chunk we
    retrieved, whose page we already know. Returns the first match in ``context_chunks``
    order (relevance-ordered, so the most relevant copy wins), else None. TOC/index
    chunks are skipped — they list every term verbatim and would mis-attribute."""
    toks = _significant_tokens(line)
    if not toks:
        return None
    for c in context_chunks:
        content = (c.get("content") or "")
        if _is_toc_chunk(content):
            continue
        low = content.lower()
        if all(t in low for t in toks):
            return c
    return None


def _attribution_chip(qnum: int, chunk: dict, line: str) -> list[str]:
    """Nav-only citation chip for a post-hoc attributed line: a MEDIA chunk (audio/video —
    has a ``start_time``) cites its timestamp ``[N, MM:SS]``; a PDF chunk cites its page
    ``[N, S. X]``. Media also carries a transcript ``page_number`` (segment index) which
    must NOT be rendered as a page, so the start_time is checked FIRST. No span offset, no
    keyword — clicking only scrolls to the page/timestamp. `line` kept for stability/logging."""
    st = chunk.get("start_time")
    if st is not None:
        return [f"[{qnum}, {_format_timestamp(st)}]"]
    page = chunk.get("page_number")
    return [f"[{qnum}, S. {page}]"] if page is not None else []


def _append_scope_anchor(text: str, qnum: int, page: int) -> str:
    """Append ONE nav-only page chip at the very bottom of a SINGLE-page scope summary.

    A single-page PDF scope ("fasse Seite 5 zusammen") would otherwise chip every line
    with the SAME page the user explicitly named — pure noise in nav-only mode. We skip
    per-line attribution for that case and append this one click-to-page anchor instead,
    so a single jump-to-page link remains. The frontend renders ``[N, S. X]`` as a chip."""
    return f"{text.rstrip()}\n\n[{qnum}, S. {page}]"


def _is_label_line(line: str) -> bool:
    """A lead-in / label line that ends with a colon once trailing markdown emphasis and
    whitespace are stripped (``**Quelle nach dem AGG:**``, ``Sanktionen:``). It introduces
    the content on the following line(s) rather than making a claim itself, so it must NOT
    carry a citation chip — the chip would just dangle after the colon and the real claim
    below is cited anyway. Colon-only (after stripping) → language-agnostic, no word lists."""
    s = re.sub(r"[*_`~\s]+$", "", line.rstrip())
    return s.endswith(":")


def _needs_attribution(line: str) -> bool:
    """Whether a GENERIC answer line gets post-hoc attribution: substantial enough, not a
    table delimiter, not a colon-ending label, AND not already cited. Exposed so the caller
    can pre-collect the exact same candidate lines and embed them in ONE batch call (instead
    of one embed per line).

    The delimiter guard is load-bearing: a real GFM delimiter is `|--------|--------|`, whose
    dedup key is the dash/pipe run itself (≥16 chars) — substantial by length alone. Without
    this it passes the gate and gets a chip injected INSIDE the row, which makes GFM stop
    parsing the block as a table (it collapses to a paragraph in the UI). A short `|-|-|`
    happens to fall under the length floor, which is why this only bites real-world tables."""
    return (len(_line_dedup_key(line)) >= _DEDUP_MIN_KEY_LEN
            and not _is_table_delim(line)
            and not _is_label_line(line)
            and not _HAS_CITE.search(line.rstrip()))


def _is_table_row(line: str) -> bool:
    """A Markdown table row: trimmed line starts and ends with a pipe."""
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _is_table_delim(line: str) -> bool:
    """A Markdown table delimiter row, e.g. ``|---|---|`` / ``|:--|--:|`` (only
    pipes, dashes, colons, spaces)."""
    s = line.strip()
    return bool(s) and set(s) <= set("|-: ")


def _place_chip(line: str, chip_str: str) -> str:
    """Attach ``chip_str`` to a line. For a table row the chip goes INSIDE the last
    cell (before the closing pipe) so the row keeps its pipe-defined column count and
    GFM still parses the block as a table; otherwise it is appended after the line."""
    if _is_table_row(line):
        return re.sub(r"\s*\|\s*$", f" {chip_str} |", line.rstrip())
    return f"{line.rstrip()} {chip_str}"


def _line_candidates(line: str, search_one, context_chunks: Optional[list[dict]],
                     seen_pages_by_source: Optional[dict]) -> list[dict]:
    """Retrieved (seen), non-TOC source chunks that could ground ``line``, closest-first.

    If an EXACT verbatim chunk exists (a name/email/number we already retrieved, whose
    page we know), it is the SOLE high-confidence candidate — semantic near-misses on
    other pages are suppressed. Otherwise the seen semantic hits, sorted by distance: a
    reworded/synthesised line may legitimately draw from several passages, so the caller
    can attach a chip per distinct source/page."""
    exact = _exact_attribution_chunk(line, context_chunks) if context_chunks else None
    if exact is not None and _is_seen(exact, seen_pages_by_source):
        e = dict(exact)
        e["vec_distance"] = 0.0  # verbatim presence == certain
        return [e]
    cands = [h for h in (search_one(line) or [])
             if h.get("vec_distance") is not None
             and not _is_toc_chunk(h.get("content") or "")
             and _is_seen(h, seen_pages_by_source)]
    cands.sort(key=lambda h: h["vec_distance"])
    return cands


def _chips_for_line(cands: list[dict], source_id_to_qnum: dict,
                    max_distance: float,
                    guarantee_dist: float = _GUARANTEE_MAX_DIST) -> list[str]:
    """Build the chip list for ONE line from its closest-first candidates.

    The first usable candidate is the GUARANTEE chip (closest retrieved chunk, accepted
    up to ``guarantee_dist`` so a grounded claim is never left chip-less); each further
    chip must be a DISTINCT source/page within the normal ``max_distance`` (a genuine
    additional contributing passage), capped at ``_MAX_CHIPS_PER_LINE``. Overview mode
    passes ``guarantee_dist = max_distance`` so a loose, misleading single chip on a
    many-source synthesis line is dropped instead of guaranteed."""
    chips: list[str] = []
    keys: set = set()
    primary_d: Optional[float] = None
    for h in cands:
        qnum = source_id_to_qnum.get(h.get("source_id"))
        if qnum is None:
            continue
        d = h.get("vec_distance")
        d = 1.0 if d is None else d
        if primary_d is None:
            if d > guarantee_dist:  # closest seen chunk too far → no chip at all
                break
            primary_d = d                # the guarantee chip; anchors the relative gate
        elif d > min(max_distance, primary_d + _MULTI_CHIP_MAX_DELTA):
            break                        # additional sources must be CLOSE to the best
        st = h.get("start_time")
        if st is not None:                  # media: dedup by timestamp, NOT the transcript
            key = (qnum, "t", st)           # segment index that lives in page_number
        else:
            key = (qnum, h.get("page_number"))
        if key in keys:
            continue
        c = _attribution_chip(qnum, h, "")
        if c:
            chips.extend(c)
            keys.add(key)
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
    return chips


def _is_continuation(line: str) -> bool:
    """A non-blank line that CONTINUES the previous claim block (wrapped prose / a second
    sentence of the same bullet) rather than starting a new one. New list items, headings,
    table rows and blank lines start a fresh block. Used so a bullet's chips go at the
    block END, never mid-bullet."""
    s = line.strip()
    if not s or _is_table_row(line):
        return False
    ls = line.lstrip()
    if ls.startswith("#"):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True


def _attr_blocks(lines: list[str]) -> list[list[int]]:
    """Group line indices into attribution BLOCKS. A claim block = one bullet/paragraph
    line PLUS the continuation lines that render as part of it (its chips go on the
    block's LAST line). Blank/heading lines and each table row are their own block."""
    blocks: list[list[int]] = []
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        if _is_table_row(lines[i]) or lines[i].lstrip().startswith("#"):
            blocks.append([i])
            i += 1
            continue
        blk = [i]
        i += 1
        while i < n and _is_continuation(lines[i]):
            blk.append(i)
            i += 1
        blocks.append(blk)
    return blocks


_PAREN_RE = re.compile(r"\(([^)]{1,80})\)")
# A law abbreviation: ALL-CAPS (ZPO, UWG, SGB, GG) or a word with an INTERNAL capital
# (UrhG, MarkenG, VwVfG, BImSchG, StBerG, BauGB, FeV). Plain Title-case nouns
# (Wortmarken, Berechnung) are NOT matched, so a descriptive paren is not read as a law.
_LAW_ABBR_RE = re.compile(r"[A-ZÄÖÜ]{2,}[0-9]*|[A-ZÄÖÜ][A-Za-zäöüß0-9]*[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9]*")

def _names_many_laws(text: str, threshold: int = 3) -> bool:
    """True when a line names >= ``threshold`` DISTINCT law abbreviations inside parentheses
    (e.g. "… (ZPO) … (MarkenG) … (§ 21 StBerG) … (z. B. UWG, UmwG) …"). That is a GENERIC
    synthesis/enumeration over many sources that no single citation chip can meaningfully
    point at, so overview mode leaves it chip-free instead of attaching one misleading link.
    Only law-shaped abbreviations count, not Title-case descriptive words. A spelled-out
    name-list ("Maler, Flugtechnik, …") is handled separately by ``_enum_chip_unbacked``,
    which is content-gated — capitalisation alone cannot tell a multi-source enumeration
    from an in-source example list ("(Ärzte, Zahnärzte, Tierärzte, Apotheker)")."""
    abbrs: set = set()
    for m in _PAREN_RE.finditer(text or ""):
        abbrs.update(_LAW_ABBR_RE.findall(m.group(1)))
    return len(abbrs) >= threshold


# A SPELLED-OUT enumeration the paren-abbreviation rule misses: a tight comma-run of
# capitalised single-word items ("Maler, Flugtechnik, Heimarbeiter, Bauwirtschaft"). Each
# comma segment is exactly ONE capitalised token, so ordinary prose noun-lists carrying
# prepositions or multi-word phrases ("Anforderungen an Prüfungen, … einschließlich
# Gewichtung") break the run and do NOT match. ``{3,}`` = >= 3 commas = >= 4 items.
# Language-agnostic: keys only on capitalisation + commas, no per-language word list.
_CAP_TOKEN = r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]+"
_ENUM_LIST_RE = re.compile(rf"{_CAP_TOKEN}(?:\s*,\s*{_CAP_TOKEN}){{3,}}")
_ENUM_BACKED_MIN = 0.5  # fraction of items the cited chunk must contain to keep the chip


def _enum_chip_unbacked(text: str, content: str) -> bool:
    """True when ``text`` spells out a >= 4-item name-list ("… Maler, Flugtechnik,
    Heimarbeiter, Bauwirtschaft …") AND the single chunk we would cite (``content``)
    does NOT actually contain most of those items — i.e. the chip would point at a page
    that backs only one of the listed things, the misleading "one chip on a many-source
    enumeration" case. The content gate is what separates that from an in-source example
    list ("(Ärzte, Zahnärzte, Tierärzte, Apotheker)" whose chunk literally enumerates all
    four): there the items ARE in the cited chunk, so the chip stays. Capitalisation alone
    cannot tell the two apart, so we check the cited chunk's text, not just the shape."""
    m = _ENUM_LIST_RE.search(text or "")
    if not m:
        return False
    items = [t.strip() for t in m.group(0).split(",")]
    if len(items) < 4:
        return False
    low = (content or "").lower()
    present = sum(1 for it in items if it.lower() in low)
    return present < len(items) * _ENUM_BACKED_MIN


def _attribute_generic_text(text: str, search_one, source_id_to_qnum: dict, offset_fn=None, *,
                            seen_pages_by_source=None, context_chunks=None, overview: bool = False,
                            max_distance: float = _GENERIC_ATTRIB_MAX_DIST) -> str:
    """Re-ground each substantial, uncited line of a GENERIC answer.

    Two-stage grounding per line:
    1. **Exact match against the already-retrieved chunks** (``context_chunks``): if
       every significant token of the line is verbatim in a chunk we sent, that chunk
       is the source. Catches names/emails/numbers that embed poorly — we already have
       those chunks with their pages, so there is no need to re-search for them.
    2. **Semantic search** (``search_one(line)`` → ranked hits with vec_distance /
       source_id / page_number / content / optional start_time) for paraphrased prose
       the model reworded, gated by ``max_distance``.

    ``offset_fn`` is accepted for backwards-compatibility but IGNORED — all chips are
    nav-only. Short/heading lines and lines that already carry a chip are left
    untouched; an unsupported line (gate) gets no chip.

    ``seen_pages_by_source`` (optional) maps source_id -> set of PDF page numbers that
    were actually retrieved into context. When given, a chip is only emitted if the
    attributed source/page was in that set (cross-check). Media sources (page_number is
    None) pass the check whenever their source_id is present in the mapping.

    The candidate gate is ``_needs_attribution`` — the caller uses the same predicate
    to batch-embed all candidate lines up front, so ``search_one`` only has to look up
    a precomputed vector here.

    GUARANTEE + MULTI-CHIP: every substantial claim of a *grounded* answer gets at least
    one chip (closest retrieved chunk, up to ``_GUARANTEE_MAX_DIST``) — a claim built
    from the sent chunks is never left without a source link. A reworded/synthesised line
    that legitimately draws from several retrieved passages gets a chip PER distinct
    source/page (up to ``_MAX_CHIPS_PER_LINE``). "Grounded" = at least one substantial
    line lands within ``max_distance`` (or has an exact verbatim match); the honest
    "not in the sources" answer never does, so it stays uncited as before."""
    lines = text.split("\n")
    # Pass 1: gather seen candidates per substantial line; decide if the answer is grounded.
    cand_by_idx: dict[int, list[dict]] = {}
    grounded = False
    for i, line in enumerate(lines):
        if not _needs_attribution(line):
            continue
        # A table HEADER row (next line is the |---| delimiter) is a column label, not a
        # claim — never cite it (citing it would also dirty the column titles).
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _is_table_row(line) and _is_table_delim(nxt):
            continue
        cands = _line_candidates(line, search_one, context_chunks, seen_pages_by_source)
        if not cands:
            continue
        cand_by_idx[i] = cands
        d0 = cands[0].get("vec_distance")
        if d0 is not None and d0 <= max_distance:
            grounded = True
    # Pass 2: emit chips at the END of each BLOCK (a bullet/paragraph + its continuation
    # lines), never mid-block, with contributing sources DEDUPED across the whole block —
    # so a two-sentence bullet shows its chips once, at the end, not after each sentence.
    # An UNGROUNDED answer (honest "not contained") gets none.
    out = list(lines)
    if grounded:
        # Overview (GENERIC): no loose GUARANTEE chip — cite only a genuinely close single
        # source (gate = max_distance), and leave a multi-law enumeration line chip-free,
        # since one chip on a 100-source synthesis is misleading. SPECIFIC is unchanged.
        guarantee = max_distance if overview else _GUARANTEE_MAX_DIST
        for blk in _attr_blocks(lines):
            block_text = " ".join(lines[i] for i in blk)
            if overview and _names_many_laws(block_text):
                continue
            agg: list[dict] = []
            for idx in blk:
                agg.extend(cand_by_idx.get(idx, []))
            if not agg:
                continue
            agg.sort(key=lambda h: h["vec_distance"] if h.get("vec_distance") is not None else 1.0)
            # Overview: a spelled-out name-list whose cited chunk backs only one item is the
            # misleading "one chip on a many-source enumeration" case → leave it chip-free.
            # Content-gated so an in-source example list (chunk holds all items) keeps its chip.
            if overview and _enum_chip_unbacked(block_text, agg[0].get("content") or ""):
                continue
            chips = _chips_for_line(agg, source_id_to_qnum, max_distance, guarantee_dist=guarantee)
            if chips:
                last = blk[-1]
                # Table data row -> chip(s) INSIDE the last cell (keeps GFM column count
                # intact); otherwise appended after the block's last line.
                out[last] = _place_chip(lines[last], " ".join(chips))
    return "\n".join(out)


_INLINE_CITE_STRIP_RE = re.compile(r"\s*[\[【][^\]】\n]*(?:#\s*\d|S\.\s*\d|\d{1,2}:\d{2})[^\]】\n]*[\]】]")


def _strip_inline_citation_chips(text: str) -> str:
    """Remove citation-shaped brackets (chunk-id, page or timestamp) from a line. Used
    for the GENERIC live stream: we show clean text while streaming and attach the
    post-hoc semantic-attribution chips only in the final answer."""
    out = _INLINE_CITE_STRIP_RE.sub("", text)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).rstrip()


def _load_transcript_segments(source: dict) -> list[dict]:
    """Load Whisper segments from the _transcript.txt artifact next to a media source.

    Returns list of {"start": float, "end": float, "text": str} or [] on any error.
    """
    file_path = source.get("file_path") or ""
    if not file_path:
        return []
    base_key = file_path.rsplit(".", 1)[0]
    transcript_key = base_key + "_transcript.txt"
    try:
        from src.storage import get_file
        text = get_file(transcript_key).decode("utf-8")
    except Exception as e:
        logger.debug("transcript artifact unavailable for source {}: {}", source.get("id"), e)
        return []
    segments: list[dict] = []
    for line in text.splitlines():
        m = _TRANSCRIPT_LINE.match(line.strip())
        if m:
            segments.append({
                "start": _parse_ts(m.group(1)),
                "end": _parse_ts(m.group(2)),
                "text": m.group(3).strip(),
            })
    return segments


def _enrich_media_content(chunk: dict, segments: list[dict]) -> str:
    """Inject inline `(MM:SS)` markers at segment boundaries within a media chunk's content.

    Gives the LLM finer-grained timestamps to cite than just the chunk's start_time,
    so answers about content mid-chunk can reference the correct moment.
    Falls back to the original content if segments can't be aligned.
    """
    content = chunk.get("content") or ""
    if chunk.get("start_time") is None or chunk.get("end_time") is None or not segments:
        return content
    tol = 0.5
    relevant = [
        s for s in segments
        if chunk["start_time"] - tol <= s["start"] <= chunk["end_time"] + tol
    ]
    if len(relevant) < 2:
        return content
    return " ".join(f"({_format_timestamp(s['start'])}) {s['text']}" for s in relevant)

def _require_own_workspace(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] != user_id:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace

def _require_workspace_access(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allow owner OR enrolled student. Used for read-only workspace info."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_student_enrolled(workspace["id"], user_id):
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

def _save_source_file(user_id: int, workspace_uuid: str, source_uuid: str, ext: str, data: bytes) -> str:
    from src.storage import aia_source_key
    key = aia_source_key(user_id, workspace_uuid, source_uuid, ext)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)

def _delete_source_files_for_workspace(workspace: dict) -> None:
    sources = db.get_aia_sources_by_workspace(workspace["id"])
    for source in sources:
        try:
            delete_file(source["file_path"])
        except Exception as e:
            logger.warning("KI Tutor: could not delete file {}: {}", source["file_path"], e)

def _resolve_source_ids(
    workspace: dict, source_uuids: list[str], max_count: int = 3,
    locale: str = DEFAULT_LOCALE,
) -> list[int]:
    """Resolve source UUIDs to DB IDs, enforce max count."""
    if len(source_uuids) > max_count:
        raise HTTPException(status_code=400, detail=t("ai.source.maxAllowed", locale, max=max_count))
    ids = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source and source["workspace_id"] == workspace["id"] and source["status"] == "ready":
            ids.append(source["id"])
    if not ids:
        raise HTTPException(status_code=400, detail=t("ai.source.noValidSelected", locale))
    return ids

def _term_appears_in_text(term: str, text_lower: str) -> bool:
    """Check if term appears literally or as a lemma/stem prefix in the text.
    Allows LLM to return Grundform (e.g. "erhöhen") when text has inflected
    form ("erhöht", "zu erhöhen"). Rejects terms that share only a weak prefix.
    """
    t = term.lower().strip()
    if not t:
        return False
    if t in text_lower:
        return True
    stem_len = max(5, len(t) * 3 // 4)
    stem = t[:stem_len]
    return bool(re.search(r"\b" + re.escape(stem), text_lower))


import re as _re

# A line "already has a citation" if it ends with a chip token — optionally followed
# by a markdown table cell's closing pipe (the chip can sit inside the last cell).
_HAS_CITE = _re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*\|?\s*$")
