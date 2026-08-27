"""Shared helpers for KI-Assistent routes."""

import asyncio
import math
import re
import subprocess
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException
from loguru import logger
from langfuse.decorators import langfuse_context

from src import database as db
from src.i18n import DEFAULT_LOCALE, t
from src.services.aia_literal_evidence import pin_words
from src.services.aia_segment_pick import best_index, rare_stems, rarity_weights
from src.services.aia_transcript_offsets import TranscriptIndex
from src.storage import (
    aia_transcript_key,
    delete_aia_workspace_folder,
    get_file,
    save_aia_source_from_path,
)

# Repairs citations where the model closes the bracket too early.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")
_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")

# Drops empty 【…】 brackets, real citations and CJK text stay.
_STRAY_LENTICULAR_RE = re.compile(
    r"\s?【(?![^】]*(?:S\.\s*\d|\d{1,2}:\d{2}|[぀-鿿가-퟿]))[^】]*】"
)


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations and drop stray 【…】 placeholders."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    text = _STRAY_LENTICULAR_RE.sub("", text)
    return text


# Arrows between two steps out, they hide the verb.
_ARROW_CONNECTOR_RE = re.compile(r"[ \t]*(?:→|⟶|➔|➜|-->|->|=>)[ \t]*")


def _strip_arrow_connectors(text: str) -> str:
    """Drop arrow connectors, keeping one separating space."""
    return _ARROW_CONNECTOR_RE.sub(" ", text)


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
    """Remuxes MP4 so the browser can play right away instead of downloading first."""
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


# The same helpers on file paths so a large upload need not go into memory.

def _convert_office_to_pdf_path(src_path: str, ext: str, out_dir: str, locale: str = DEFAULT_LOCALE) -> str:
    """Converts a docx or pptx file to PDF via LibreOffice."""
    result = subprocess.run(
        ["libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
         "--outdir", out_dir, src_path],
        capture_output=True, text=True, timeout=180,
    )
    pdf_path = Path(out_dir) / (Path(src_path).stem + ".pdf")
    if not pdf_path.exists():
        logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
        raise HTTPException(status_code=500, detail=t("ai.source.pdfConversionFailed", locale))
    return str(pdf_path)


def _mp4_faststart_path(src_path: str, out_dir: str) -> str:
    """Remuxes an MP4 file on disk for immediate playback."""
    dst = Path(out_dir) / "faststart.mp4"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path,
             "-c", "copy", "-movflags", "+faststart", str(dst)],
            capture_output=True, text=True, timeout=600,
        )
    except Exception as e:
        logger.warning("KI Tutor: faststart remux exception: {}", e)
        return src_path
    if result.returncode != 0 or not dst.exists():
        logger.warning("KI Tutor: faststart remux failed (rc={}): {}", result.returncode, result.stderr[:200])
        return src_path
    return str(dst)


def _count_pages_path(ext: str, path: str) -> int | None:
    """Page/slide count for a PDF/PPTX on disk, None for other formats."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path)
            count = len(doc)
            doc.close()
            return count
        if ext == ".pptx":
            from pptx import Presentation
            return len(Presentation(path).slides)
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
    """Prepares text for the verbatim keyword comparison."""
    s = unicodedata.normalize("NFKC", s).casefold()
    for hy in ("‐", "‑", "‒", "–", "—", "−"):
        s = s.replace(hy, "-")
    return re.sub(r"\s+", " ", s).strip()


# Recognises a table-of-contents line by the dot leader before the page number.
_TOC_LEADER_RE = re.compile(r"(?:\.\s*){4,}\d{1,4}")


def _strip_toc_lines(text: str) -> str:
    """Drops lines that are table-of-contents entries."""
    if not text or "." not in text:
        return text
    return "\n".join(ln for ln in text.split("\n") if not _TOC_LEADER_RE.search(ln))


def _is_toc_chunk(content: str, *, min_chars: int = 20, max_kept_ratio: float = 0.4) -> bool:
    """True when a chunk is almost only a table of contents and therefore no evidence target."""
    raw = (content or "").replace(" ", "").replace("\n", "")
    if len(raw) < min_chars:
        return False
    kept = _strip_toc_lines(content).replace(" ", "").replace("\n", "")
    return len(kept) <= len(raw) * max_kept_ratio


# Guard against repetition loops, lines are compared by their prose.
_DEDUP_BRACKET_RE = re.compile(r"[\[【][^\]】]*[\]】]")
_DEDUP_MIN_KEY_LEN = 16


def _line_dedup_key(line: str) -> str:
    """Comparison form of a line: chips and bullets out, then normalise."""
    s = _DEDUP_BRACKET_RE.sub("", line)
    s = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", s)
    return _norm_for_match(s)


class _RepetitionGuard:
    """Detects a repetition loop of the model across whole lines."""

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
    """True when the end of the buffer repeats a short unit without a line break."""
    tail = buf[-window:]
    n = len(tail)
    for unit in range(min_unit, max_unit + 1):
        if unit * repeats > n:
            break
        seg = tail[-unit:]
        if seg.strip() and tail.endswith(seg * repeats):
            return True
    return False


# Folds a short unit repeated three times in a row.
_COLLAPSE_REPEAT_RE = re.compile(r"(.{6,160}?)(?:\1){3,}", re.DOTALL)


def _collapse_repeats(text: str) -> str:
    """Folds a unit repeated three or more times down to one copy."""
    if len(text) > 60000:
        return text
    return _COLLAPSE_REPEAT_RE.sub(lambda m: m.group(1), text)


def _dedup_repeated_lines(text: str) -> str:
    """Drops later duplicates of a content-bearing line."""
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


# A page ("S. 6" / "S.6") or timestamp ("08:58" / "1:05:19") locator, optional leading pipe.
_SRC_LOCATOR_RE = re.compile(r"\|?\s*(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)\s*", re.IGNORECASE)
_LIST_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _is_pure_source_ref(line: str, names: list[str]) -> bool:
    """True when a line is only a source name plus a page or time reference."""
    s = _LIST_BULLET_RE.sub("", line.strip())
    if not s:
        return False
    low = s.lower()
    hit = next((nm for nm in names if nm and nm.lower() in low), None)
    if not hit:
        return False
    rest = low.replace(hit.lower(), " ")
    rest = _SRC_LOCATOR_RE.sub(" ", rest)
    rest = re.sub(r"[|,;:_\-\s]+", "", rest)
    return len(rest) <= 2


def _strip_source_list(text: str, source_filenames: list[str]) -> str:
    """Removes a source list written by the model together with its heading."""
    names: list[str] = []
    for f in source_filenames:
        if not f:
            continue
        names.append(f)
        stem = f.rsplit(".", 1)[0]
        if stem and stem != f:
            names.append(stem)
    if not names:
        return text
    lines = text.split("\n")
    is_ref = [_is_pure_source_ref(ln, names) for ln in lines]
    keep = [True] * len(lines)
    n = len(lines)
    i = 0
    while i < n:
        if not is_ref[i]:
            i += 1
            continue
        j, cnt, last = i, 0, i
        while j < n and (is_ref[j] or not lines[j].strip()):
            if is_ref[j]:
                cnt += 1
                last = j
            j += 1
        if cnt >= 2:
            for k in range(i, last + 1):
                keep[k] = False
            p = i - 1
            while p >= 0 and not lines[p].strip():
                p -= 1
            if p >= 0 and lines[p].strip().endswith(":") and len(lines[p].strip()) <= 40:
                keep[p] = False
        i = j
    return "\n".join(ln for ln, k in zip(lines, keep) if k).strip()


def _strip_tiny_tables(text: str) -> str:
    """Drops a table with fewer than two data rows when enough text remains."""
    lines = text.split("\n")
    keep = [True] * len(lines)
    n = len(lines)
    i = 0
    while i < n:
        if _is_table_row(lines[i]) and i + 1 < n and _is_table_delim(lines[i + 1]):
            j = i + 2
            data = 0
            while j < n and _is_table_row(lines[j]):
                data += 1
                j += 1
            if data < 2:
                for k in range(i, j):
                    keep[k] = False
            i = j
        else:
            i += 1
    remaining = "\n".join(ln for ln, k in zip(lines, keep) if k).strip()
    return remaining if len(remaining) >= 15 else text


# Overview answers are backed afterwards by search, with a distance threshold.
_GENERIC_ATTRIB_MAX_DIST = 0.6
# Looser threshold so no line of a backed answer stays without a chip.
_GUARANTEE_MAX_DIST = 0.85
# How many candidates the search must return before picking.
_ATTRIB_CANDIDATES = 40
_MAX_CHIPS_PER_LINE = 3
# A further chip only comes along when its distance is practically that of the best.
_MULTI_CHIP_MAX_DELTA = 0.04
# Ceiling of chips per chip position, matching the display in the browser.
_COVERAGE_MAX_CHIPS_PER_LINE = 3
# How many looked-up chunks may push ahead per line.
_MAX_LITERAL_CANDIDATES = 4
# Distance threshold below which a line counts as a refusal and gets no chip.
_REFUSAL_MAX_DIST = 0.60


def _cos_dist(a, b) -> float:
    """Cosine distance of two equally long vectors, 1.0 on degenerate input."""
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 1.0
    return 1.0 - dot / (math.sqrt(na) * math.sqrt(nb))


def _refusal_lines(cands: list[str], vec_by_line: dict, sentinel_vecs: list,
                   max_dist: float = _REFUSAL_MAX_DIST) -> set:
    """Which candidate lines are a refusal, measured by distance to the model sentence."""
    if not sentinel_vecs:
        return set()
    flagged: set = set()
    for ln in cands:
        v = vec_by_line.get(ln)
        if v is None:
            continue
        if any(_cos_dist(v, sv) <= max_dist for sv in sentinel_vecs):
            flagged.add(ln)
    return flagged


def is_refusal_answer(text: str, embed_fn, sentinels: list[str],
                      max_dist: float = _REFUSAL_MAX_DIST) -> bool:
    """True when the whole answer is a refusal."""
    cleaned = (text or "").strip()
    if not cleaned or not sentinels:
        return False
    try:
        vecs = embed_fn([cleaned] + sentinels)
    except Exception:
        return False
    if len(vecs) != 1 + len(sentinels):
        return False
    answer_vec, sentinel_vecs = vecs[0], vecs[1:]
    return any(_cos_dist(answer_vec, sv) <= max_dist for sv in sentinel_vecs)


def _is_seen(chunk: dict, seen_pages_by_source: Optional[dict]) -> bool:
    """True when source and page of this chunk really were in the model's context."""
    if seen_pages_by_source is None:
        return True
    pages = seen_pages_by_source.get(chunk.get("source_id"))
    if pages is None:
        return False
    if chunk.get("start_time") is not None:   # media: source-level cross-check (no page)
        return True
    pg = chunk.get("page_number")
    return pg is None or pg in pages


def _scope_chunk_ids(scope_chunks: Optional[list[dict]]) -> Optional[set]:
    """The chunk ids the model saw when a page or time reference was explicit."""
    if not scope_chunks:
        return None
    ids = {c["id"] for c in scope_chunks if c.get("id") is not None}
    return ids or None


def _pick_attribution(hits: list[dict], max_distance: float,
                      seen_pages_by_source: Optional[dict] = None) -> Optional[dict]:
    """The nearest hit within the threshold, otherwise None and therefore no chip."""
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
# Keep word characters and umlauts, allow at sign, dot and inner hyphen.
_TOKEN_RE = re.compile(r"[0-9A-Za-zÄÖÜäöüß][0-9A-Za-zÄÖÜäöüß@.\-]*")


def _significant_tokens(line: str) -> list[str]:
    """The distinguishing content words of a line."""
    s = re.sub(r"[*_`~#>]+", " ", line)
    out: list[str] = []
    for w in _TOKEN_RE.findall(s):
        wl = w.strip(".-").lower()
        if len(wl) >= 4 and wl not in _ATTR_STOP:
            out.append(wl)
    return out


def _exact_attribution_chunk(line: str, context_chunks: list[dict]) -> Optional[dict]:
    """Backs a line by its verbatim occurrence in a chunk that was already fetched."""
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


# How much of a word start counts when comparing with a transcript segment.
_SEGMENT_STEM_CHARS = 6

# How many word stems a segment must carry to fix the timestamp.
_SEGMENT_MIN_STEM_HITS = 2
# One stem carries the timestamp alone when it occurs rarely enough.
_SEGMENT_RARE_MAX_DF = 3
# For that the source needs enough segments per allowed occurrence.
_SEGMENT_RARE_SEGMENTS_PER_HIT = 25

# Numbers count as a feature of their own, even when short.
_SEGMENT_MIN_NUM_CHARS = 2


_SEGMENT_HYPHEN_RE = re.compile(r"-+")


def _norm_for_segment(s: str) -> str:
    """Like :func:`_norm_for_match`, but the hyphen counts as a space."""
    return re.sub(r"\s+", " ", _SEGMENT_HYPHEN_RE.sub(" ", _norm_for_match(s))).strip()


def _segment_stems(line: str) -> set[str]:
    """Features of an answer line for the segment comparison."""
    line = _SEGMENT_HYPHEN_RE.sub(" ", line)
    stems = {_norm_for_segment(t)[:_SEGMENT_STEM_CHARS] for t in _significant_tokens(line)}
    for w in _TOKEN_RE.findall(re.sub(r"[*_`~#>]+", " ", line)):
        wl = _norm_for_segment(w.strip(".,-:;"))
        if len(wl) >= _SEGMENT_MIN_NUM_CHARS and any(ch.isdigit() for ch in wl):
            stems.add(wl)
    stems.discard("")
    return stems


def _chunk_segments(chunk: dict, segments: list[dict]) -> list[dict]:
    """The Whisper segments of a media chunk, matched up by their order."""
    if chunk.get("start_time") is None or not segments:
        return []
    return TranscriptIndex(segments).segments_of(chunk)


def _line_segment_start(line: str, chunk: dict, segments: list[dict]) -> Optional[float]:
    """Start time of the segment carrying the cited line, or None."""
    segs = _chunk_segments(chunk, segments)
    if len(segs) < 2:
        return None
    stems = _segment_stems(line)
    if not stems:
        return None
    treffer = [[stem for stem in stems if stem in _norm_for_segment(s.get("text") or "")]
               for s in segs]
    selten = rare_stems(chunk.get("source_id"), segments, _segment_stems, _norm_for_segment,
                        min(_SEGMENT_RARE_MAX_DF,
                            len(segments) // _SEGMENT_RARE_SEGMENTS_PER_HIT))
    if (max((len(t) for t in treffer), default=0) < _SEGMENT_MIN_STEM_HITS
            and not any(selten.intersection(t) for t in treffer)):
        return None
    gewichte = rarity_weights(chunk.get("source_id"), segments,
                              _segment_stems, _norm_for_segment)
    return segs[best_index(treffer, gewichte)]["start"]


def _attribution_chip(qnum: int, chunk: dict, line: str,
                      segments: Optional[list[dict]] = None) -> list[str]:
    """Source chip to jump with: a timestamp for media, a page number for PDF."""
    st = chunk.get("start_time")
    if st is not None:
        if line and segments:
            seg_start = _line_segment_start(line, chunk, segments)
            if seg_start is not None:
                st = seg_start
        return [f"[{qnum}, {_format_timestamp(st)}]"]
    page = chunk.get("page_number")
    return [f"[{qnum}, S. {page}]"] if page is not None else []


def _append_scope_anchor(text: str, qnum: int, page: int) -> str:
    """Appends exactly one page chip at the end of a single-page summary."""
    return f"{text.rstrip()}\n\n[{qnum}, S. {page}]"


def _is_label_line(line: str) -> bool:
    """A line ending in a colon only introduces and gets no chip."""
    s = re.sub(r"[*_`~\s]+$", "", line.rstrip())
    return s.endswith(":")


# A line entirely in bold counts as a heading.
_BOLD_HEADING_RE = re.compile(r"^(\*\*|__)(?:(?!\1).)+\1[\s.?!:]*$")


def _is_heading_line(line: str) -> bool:
    """A heading, as a hash or fully bold, claims nothing and gets no chip."""
    return line.lstrip().startswith("#") or bool(_BOLD_HEADING_RE.match(line.strip()))


def _needs_attribution(line: str) -> bool:
    """Whether a line can carry a chip at all."""
    return (len(_line_dedup_key(line)) >= _DEDUP_MIN_KEY_LEN
            and not _is_table_delim(line)
            and not _is_label_line(line)
            and not _is_heading_line(line)
            and not _HAS_CITE.search(line.rstrip()))


def _is_table_row(line: str) -> bool:
    """A Markdown table row: trimmed line starts and ends with a pipe."""
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _is_table_delim(line: str) -> bool:
    """A separator row of a Markdown table."""
    s = line.strip()
    return bool(s) and set(s) <= set("|-: ")


def _attach_chips(text: str, chip_str: str) -> str:
    """Puts the chip before the final period, otherwise simply at the end."""
    s = text.rstrip()
    i = len(s)
    while i > 0 and s[i - 1] in ".!?":
        i -= 1
    if 0 < i < len(s):                     # a real terminal-punctuation run with text before it
        return f"{s[:i].rstrip()} {chip_str}{s[i:]}"
    return f"{s} {chip_str}"


def _place_chip(line: str, chip_str: str) -> str:
    """Appends the chip to a line, in a table row into the last cell."""
    if _is_table_row(line):
        return re.sub(r"\s*\|\s*$", f" {chip_str} |", line.rstrip())
    return _attach_chips(line, chip_str)


def _in_scope(chunk: dict, scope_ids: Optional[set]) -> bool:
    """True when the chunk lies inside the explicit reference window, or there is none."""
    return scope_ids is None or chunk.get("id") in scope_ids


# Split on comma and semicolon only, content words from four characters count.
_CONTENT_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _content_words(text: str) -> set:
    return {w.casefold() for w in _CONTENT_WORD_RE.findall(text or "")}


def _figure_first(unit: str, cands: list[dict],
                  corpus: Optional[list[str]] = None) -> list[dict]:
    """Candidates that name a number of the line verbatim come first."""
    if not cands or not corpus:
        return cands
    from src.services.aia_literal_evidence import distinctive_tokens, figure_runs
    _, zahlen = distinctive_tokens(unit, corpus)
    if not zahlen:
        return cands
    vorne, hinten = [], []
    for c in cands:
        ziel = vorne if zahlen & figure_runs(c.get("content") or "") else hinten
        ziel.append(c)
    return vorne + hinten


def _extra_chip_earns_place(unit: str, primary: dict, extra: dict,
                            pins: frozenset = frozenset(),
                            corpus: Optional[list[str]] = None) -> bool:
    """Whether an extra chip earns its place next to the best hit."""
    from src.services.aia_literal_evidence import distinctive_tokens, figure_runs
    if corpus:
        _, zahlen = distinctive_tokens(unit, corpus)
        traegt_extra = figure_runs(extra.get("content") or "")
        traegt_primary = figure_runs(primary.get("content") or "")
        if any(z in traegt_extra and z not in traegt_primary for z in zahlen):
            return True
    if pins:
        from src.services.aia_literal_evidence import carries_pin
        fehlend = {p for p in pins if not carries_pin(p, primary.get("content") or "")}
        if not fehlend:
            return False
        return any(carries_pin(p, extra.get("content") or "") for p in fehlend)
    if primary.get("source_id") != extra.get("source_id"):
        return True
    unit_words = _content_words(unit)
    if not unit_words:
        return True
    new_words = unit_words & _content_words(extra.get("content") or "")
    return bool(new_words - _content_words(primary.get("content") or ""))


_CLAUSE_SPLIT_RE = re.compile(r"[,;]")


def _clauses(line: str) -> list[str]:
    """The content-bearing clauses of a line, without the whole line."""
    if not _CLAUSE_SPLIT_RE.search(line):
        return []
    whole = line.strip()
    out: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(line):
        p = part.strip()
        if p and p != whole and len(_line_dedup_key(p)) >= _DEDUP_MIN_KEY_LEN and p not in out:
            out.append(p)
    return out


# A sentence boundary, digits behind it rule it out.
_SENT_BOUNDARY_RE = re.compile(r"[.!?]+\s+(?=[^\W\d_])")


def _is_abbreviation_end(prefix: str) -> bool:
    """Whether the final period ends an abbreviation or number instead of a sentence."""
    tok = prefix.rstrip(".!?").split()
    if not tok:
        return False
    # Strip brackets and quotes, inner periods stay.
    tok = re.sub(r"^\W+|\W+$", "", tok[-1])
    if not tok:
        return False
    if len(tok) == 1:
        return True
    if tok.isdigit():
        return True
    if "." in tok and len(tok) <= 4:
        return True
    if tok[0].isupper() and len(tok) <= 4:
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    """Splits prose into sentences for per-sentence evidence matching."""
    s = text.strip()
    if not s:
        return []
    out: list[str] = []
    start = 0
    for m in _SENT_BOUNDARY_RE.finditer(s):
        nxt = s[m.end()] if m.end() < len(s) else ""
        if not nxt.isupper():
            continue
        # End of the sentence text = end of the terminal marks (before the whitespace).
        cut = m.end()
        while cut > start and s[cut - 1].isspace():
            cut -= 1
        if _is_abbreviation_end(s[start:cut]):
            continue
        out.append(s[start:cut].strip())
        start = m.end()
    tail = s[start:].strip()
    if tail:
        out.append(tail)
    return out


def _literal_candidates(line: str, literal_lookup, corpus: Optional[list[str]],
                        seen_pages_by_source: Optional[dict],
                        scope_ids: Optional[set]) -> list[dict]:
    """Chunks that carry a distinguishing number of the line verbatim."""
    if literal_lookup is None:
        return []
    from src.services.aia_literal_evidence import lookup_figures
    best: dict = {}
    for fig in lookup_figures(line, corpus or []):
        hits = literal_lookup(fig) or []
        for h in hits:
            cid = h.get("id")
            if _is_toc_chunk(h.get("content") or ""):
                continue
            if not _is_seen(h, seen_pages_by_source) or not _in_scope(h, scope_ids):
                continue
            # The rarest hit wins, a common date says little.
            if cid not in best or len(hits) < best[cid][0]:
                best[cid] = (len(hits), dict(h))
    ordered = sorted(best.values(), key=lambda pair: pair[0])
    return [h for _, h in ordered][:_MAX_LITERAL_CANDIDATES]


def _line_candidates(line: str, search_one, context_chunks: Optional[list[dict]],
                     seen_pages_by_source: Optional[dict],
                     scope_ids: Optional[set] = None,
                     literal_lookup=None, corpus: Optional[list[str]] = None) -> list[dict]:
    """Fetched chunks that could back the line, nearest first."""
    exact = _exact_attribution_chunk(line, context_chunks) if context_chunks else None
    if (exact is not None and _is_seen(exact, seen_pages_by_source)
            and _in_scope(exact, scope_ids)):
        e = dict(exact)
        e["vec_distance"] = 0.0  # verbatim presence == certain
        return [e]               # the verbatim chunk is the sole answer
    cands = []
    for h in (search_one(line) or []):
        if (h.get("vec_distance") is None
                or _is_toc_chunk(h.get("content") or "")
                or not _is_seen(h, seen_pages_by_source)
                or not _in_scope(h, scope_ids)):
            continue
        cands.append(h)
    cands.sort(key=lambda h: h["vec_distance"])
    # The chunk with the number moves right behind the nearest one.
    found = _literal_candidates(line, literal_lookup, corpus, seen_pages_by_source, scope_ids)
    if found:
        lit_ids = {h.get("id") for h in found if h.get("id") is not None}
        known = {c.get("id") for c in cands}
        rank = {h.get("id"): i for i, h in enumerate(found)}
        promoted = sorted([c for c in cands[1:] if c.get("id") in lit_ids],
                          key=lambda c: rank.get(c.get("id"), 99))
        others = [c for c in cands[1:] if c.get("id") not in lit_ids]
        fresh = [h for h in found if h.get("id") not in known]
        anchor = cands[0]["vec_distance"] if cands else _GENERIC_ATTRIB_MAX_DIST / 2
        for i, h in enumerate(fresh):
            h["vec_distance"] = anchor + 1e-6 * (i + 1)   # never a real distance: unranked
        for h in promoted + fresh:
            h["literal"] = True
        cands = cands[:1] + promoted + fresh + others
    return cands


def _chips_for_line(cands: list[dict], source_id_to_qnum: dict,
                    max_distance: float,
                    guarantee_dist: float = _GUARANTEE_MAX_DIST,
                    line: str = "", corpus: Optional[list[str]] = None,
                    transcript_by_source: Optional[dict[int, list[dict]]] = None) -> list[str]:
    """Builds the chips of a line: the best hit plus only practically equally near ones."""
    from src.services.aia_literal_evidence import carries_pin, pin_words
    chips: list[str] = []
    keys: set = set()
    primary_d: Optional[float] = None
    primary_content = ""
    evidence_corpus = corpus or [c.get("content") or "" for c in cands]
    # Every further chip must carry a word the best hit is missing.
    pins = pin_words(line, evidence_corpus) if line else set()
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
            primary_content = h.get("content") or ""
            pins = {p for p in pins if carries_pin(p, primary_content)}
        elif d > max_distance:
            break                        # off topic for everyone, evidence or not
        elif h.get("literal"):
            pass                         # nennt die Zahl der Aussage woertlich, das IST die Stelle
        elif d > primary_d + _MULTI_CHIP_MAX_DELTA:
            continue                     # merklich weiter weg als der beste Treffer
        elif pins and not any(carries_pin(p, h.get("content") or "") for p in pins):
            continue                     # belegt nur das Thema, nicht die Aussage
        c = _attribution_chip(qnum, h, line,
                              (transcript_by_source or {}).get(h.get("source_id")))
        if not c:
            continue
        # The finished chip is the key, it already carries source and target.
        if c[0] in keys:
            continue
        chips.extend(c)
        keys.add(c[0])
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
    return chips


def _is_continuation(line: str) -> bool:
    """A line that continues the previous block instead of starting a new one."""
    s = line.strip()
    if not s or _is_table_row(line):
        return False
    ls = line.lstrip()
    if _is_heading_line(line):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True


def _attr_blocks(lines: list[str]) -> list[list[int]]:
    """Groups lines into evidence blocks, the chip goes on the last line."""
    blocks: list[list[int]] = []
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        if _is_table_row(lines[i]) or _is_heading_line(lines[i]):
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


def _is_prose_line(line: str) -> bool:
    """An ordinary prose line, no bullet, no heading, no table."""
    ls = line.lstrip()
    if not ls.strip() or _is_table_row(line) or _is_table_delim(line):
        return False
    if _is_heading_line(line):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True


def _holds_for_every_sentence(text: str, predicate) -> bool:
    """Whether a condition holds for every sentence of the text."""
    sents = _split_sentences(text) or [text]
    return all(predicate(s) for s in sents)


def _attribution_subunits(line: str) -> list[str]:
    """The sub-units of a line that are embedded along up front."""
    if _is_prose_line(line):
        sents = _split_sentences(line)
        if len(sents) > 1:
            out: list[str] = []
            for s in sents:
                if s != line and s not in out:
                    out.append(s)
                for cl in _clauses(s):
                    if cl != line and cl not in out:
                        out.append(cl)
            return out
    return _clauses(line)


_PAREN_RE = re.compile(r"\(([^)]{1,80})\)")
# A statute abbreviation, all caps or with an inner capital.
_LAW_ABBR_RE = re.compile(r"[A-ZÄÖÜ]{2,}[0-9]*|[A-ZÄÖÜ][A-Za-zäöüß0-9]*[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9]*")

def _names_many_laws(text: str, threshold: int = 3) -> bool:
    """True when a line names many statute abbreviations and therefore has no single source."""
    abbrs: set = set()
    for m in _PAREN_RE.finditer(text or ""):
        abbrs.update(_LAW_ABBR_RE.findall(m.group(1)))
    return len(abbrs) >= threshold


# A spelled-out enumeration of at least four capitalised single words.
_CAP_TOKEN = r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]+"
_ENUM_LIST_RE = re.compile(rf"{_CAP_TOKEN}(?:\s*,\s*{_CAP_TOKEN}){{3,}}")
_ENUM_BACKED_MIN = 0.5  # fraction of items the cited chunk must contain to keep the chip


def _enum_chip_unbacked(text: str, content: str) -> bool:
    """True when a long enumeration does not occur in the cited chunk at all."""
    m = _ENUM_LIST_RE.search(text or "")
    if not m:
        return False
    items = [t.strip() for t in m.group(0).split(",")]
    if len(items) < 4:
        return False
    low = (content or "").lower()
    present = sum(1 for it in items if it.lower() in low)
    return present < len(items) * _ENUM_BACKED_MIN


def _attribute_prose_line(sentences: list[str], search_one, source_id_to_qnum: dict, *,
                          context_chunks, seen_pages_by_source, scope_ids,
                          max_distance: float, guarantee: float, overview: bool,
                          literal_lookup=None, transcript_by_source=None) -> str:
    """Rebuilds a paragraph with a source chip after every sentence."""
    corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    parts: list[str] = []
    for sent in sentences:
        chips: list[str] = []
        if _needs_attribution(sent) and not (overview and _names_many_laws(sent)):
            cands = _line_candidates(sent, search_one, context_chunks,
                                     seen_pages_by_source, scope_ids,
                                     literal_lookup=literal_lookup, corpus=corpus)
            satz_pins = frozenset(pin_words(sent, corpus or
                                            [c.get("content") or "" for c in cands]))
            if cands and not (overview and _enum_chip_unbacked(sent, cands[0].get("content") or "")):
                chips = _chips_for_line(cands, source_id_to_qnum, max_distance,
                                        guarantee_dist=guarantee, line=sent, corpus=corpus,
                                        transcript_by_source=transcript_by_source)
                seen_targets = set(chips)
                for cl in _clauses(sent):
                    if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                        break            # voll, sonst haengt die Klausel einen vierten an
                    ccands = _figure_first(sent, _line_candidates(
                        cl, search_one, context_chunks, seen_pages_by_source, scope_ids,
                        literal_lookup=literal_lookup, corpus=corpus), corpus)
                    cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                             guarantee_dist=guarantee, line=cl,
                                             corpus=corpus,
                                             transcript_by_source=transcript_by_source) if ccands else []
                    # An extra chip only stays when it covers a word of the sentence that was missing.
                    if (cchips and cchips[0] not in seen_targets
                            and _extra_chip_earns_place(sent, cands[0], ccands[0],
                                                        satz_pins, corpus=corpus)):
                        chips.append(cchips[0])
                        seen_targets.add(cchips[0])
                        if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                            break
        parts.append(_attach_chips(sent, " ".join(chips)) if chips else sent)
    return " ".join(parts)


# The searches run over a thread pool, otherwise the pause after the answer bites.
_ATTRIB_SEARCH_CONCURRENCY = 8


def _parallel_search(lines: list[str], search_fn: Callable[[str], list],
                     max_workers: int = _ATTRIB_SEARCH_CONCURRENCY) -> dict[str, list]:
    """Searches once per distinct line over a thread pool."""
    uniq = [ln for ln in dict.fromkeys(lines) if ln and ln.strip()]
    if not uniq:
        return {}

    def _one(ln: str) -> list:
        try:
            return search_fn(ln) or []
        except Exception as e:  # mirror _search_one: a failed search is just "no hits"
            logger.warning("parallel attribution search failed for a line: {}", e)
            return []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(uniq))) as ex:
        results = list(ex.map(_one, uniq))
    return dict(zip(uniq, results))


class _AttributionPrewarmer:
    """Warms the evidence caches while the answer is still streaming."""

    def __init__(self, embed_batch: Callable[[list], list],
                 search_with_vec: Callable[[str, Optional[list]], list]):
        # embed_batch embeds the whole batch in one call, search_with_vec searches with it.
        self._embed_batch = embed_batch
        self._search_with_vec = search_with_vec
        self.vecs: dict[str, list] = {}
        self.hits: dict[str, list] = {}
        self.flushes = 0            # embed calls actually spent (visibility for the rate budget)
        self._seen: set[str] = set()
        self._pending: list[str] = []
        self._lock = asyncio.Lock()

    def feed_line(self, line: str) -> None:
        """Queues a finished answer line with its sub-units for warming."""
        if not line or not _needs_attribution(line):
            return
        for unit in [line, *_attribution_subunits(line)]:
            if unit and unit.strip() and unit not in self._seen:
                self._seen.add(unit)
                self._pending.append(unit)

    def pending_count(self) -> int:
        return len(self._pending)

    async def flush(self) -> None:
        """Embeds and searches whatever is queued, exactly one run at a time."""
        async with self._lock:
            batch = self._pending
            self._pending = []
            if not batch:
                return
            try:
                vecs = await asyncio.to_thread(self._embed_batch, batch)
            except Exception as e:
                logger.warning("attribution prewarm embed failed (recomputed at attribution): {}", e)
                return
            if not vecs or len(vecs) != len(batch):
                return
            self.flushes += 1
            for unit, vec in zip(batch, vecs):
                self.vecs[unit] = vec
            searched = await asyncio.to_thread(
                _parallel_search, batch,
                lambda ln: self._search_with_vec(ln, self.vecs.get(ln)))
            self.hits.update(searched)


def _attribute_generic_text(text: str, search_one, source_id_to_qnum: dict, offset_fn=None, *,
                            seen_pages_by_source=None, context_chunks=None, overview: bool = False,
                            max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
                            refusal_lines: Optional[set] = None,
                            scope_chunks: Optional[list[dict]] = None,
                            literal_lookup=None,
                            transcript_by_source: Optional[dict[int, list[dict]]] = None) -> str:
    """Backs every content-bearing line of an overview answer after the fact."""
    lines = text.split("\n")
    # An explicit page or time reference brackets the evidence.
    scope_ids = _scope_chunk_ids(scope_chunks)
    # Measured against everything the answer was written from.
    evidence_corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    # Pass 1 collects the candidates per line and per clause.
    cand_by_idx: dict[int, list[dict]] = {}
    clause_cands_by_idx: dict[int, list[list[dict]]] = {}
    grounded = False
    for i, line in enumerate(lines):
        if not _needs_attribution(line):
            continue
        # A refusal is not a claim and never gets evidence.
        if refusal_lines and line in refusal_lines:
            continue
        # A table header row is a column label and is never backed.
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _is_table_row(line) and _is_table_delim(nxt):
            continue
        cands = _line_candidates(line, search_one, context_chunks, seen_pages_by_source,
                                 scope_ids, literal_lookup=literal_lookup,
                                 corpus=evidence_corpus)
        if not cands:
            continue
        cand_by_idx[i] = cands
        d0 = cands[0].get("vec_distance")
        if d0 is not None and d0 <= max_distance:
            grounded = True
        cc = [c for c in (_line_candidates(cl, search_one, context_chunks,
                                           seen_pages_by_source, scope_ids,
                                           literal_lookup=literal_lookup,
                                           corpus=evidence_corpus)
                          for cl in _clauses(line)) if c]
        if cc:
            clause_cands_by_idx[i] = cc
    # Pass 2 puts the chips at the block end, sources deduplicated across the block.
    out = list(lines)
    if grounded:
        # In the overview the tight threshold applies, a statute list stays chip free.
        guarantee = max_distance if overview else _GUARANTEE_MAX_DIST
        # Chips are not deduplicated across blocks, two claims may name the same spot.
        for blk in _attr_blocks(lines):
            # A prose block gets its chips per sentence instead of once at the end.
            if _is_prose_line(lines[blk[0]]):
                for _i in blk:
                    if refusal_lines and lines[_i] in refusal_lines:
                        continue
                    _sents = _split_sentences(lines[_i])
                    if _sents:
                        out[_i] = _attribute_prose_line(
                            _sents, search_one, source_id_to_qnum,
                            context_chunks=context_chunks, seen_pages_by_source=seen_pages_by_source,
                            scope_ids=scope_ids, max_distance=max_distance,
                            guarantee=guarantee, overview=overview,
                            literal_lookup=literal_lookup,
                            transcript_by_source=transcript_by_source)
                continue
            block_text = " ".join(lines[i] for i in blk)
            if overview and _holds_for_every_sentence(block_text, _names_many_laws):
                continue
            agg: list[dict] = []
            for idx in blk:
                agg.extend(cand_by_idx.get(idx, []))
            if not agg:
                continue
            agg.sort(key=lambda h: h["vec_distance"] if h.get("vec_distance") is not None else 1.0)
            # In the overview an enumeration whose evidence carries only one item stays chip free.
            _cited = agg[0].get("content") or ""
            if overview and _holds_for_every_sentence(
                    block_text, lambda s: _enum_chip_unbacked(s, _cited)):
                continue
            chips = _chips_for_line(agg, source_id_to_qnum, max_distance,
                                    guarantee_dist=guarantee, line=block_text,
                                    corpus=evidence_corpus,
                                    transcript_by_source=transcript_by_source)
            # One coverage chip per clause so every fact gets a reference.
            if not _is_table_row(lines[blk[-1]]):
                seen_targets = set(chips)
                for idx in blk:
                    for ccands in clause_cands_by_idx.get(idx, []):
                        if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                            break        # voll, sonst haengt die Klausel einen vierten an
                        ccands = _figure_first(block_text, ccands, evidence_corpus)
                        cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                                 guarantee_dist=guarantee, line=block_text,
                                                 corpus=evidence_corpus,
                                                 transcript_by_source=transcript_by_source)
                        # Here too an extra chip must cover something the best hit does not carry.
                        if (cchips and cchips[0] not in seen_targets
                                and _extra_chip_earns_place(block_text, agg[0], ccands[0],
                                                            corpus=evidence_corpus)):
                            chips.append(cchips[0])
                            seen_targets.add(cchips[0])
                            if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                                break
                    if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                        break
            if chips:
                last = blk[-1]
                # In a table row the chip goes into the last cell, otherwise at the block end.
                out[last] = _place_chip(lines[last], " ".join(chips))
    return "\n".join(out)


_INLINE_CITE_STRIP_RE = re.compile(r"\s*[\[【][^\]】\n]*(?:#\s*\d|S\.\s*\d|\d{1,2}:\d{2})[^\]】\n]*[\]】]")


def _strip_inline_citation_chips(text: str) -> str:
    """Removes citation-shaped brackets from a line."""
    out = _INLINE_CITE_STRIP_RE.sub("", text)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).rstrip()


def _load_transcript_segments(source: dict) -> list[dict]:
    """Loads the Whisper segments from the transcript file next to a media source."""
    file_path = source.get("file_path") or ""
    if not file_path:
        return []
    transcript_key = aia_transcript_key(file_path)
    try:
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
    """Puts timestamps on the segment boundaries inside a media chunk."""
    content = chunk.get("content") or ""
    relevant = _chunk_segments(chunk, segments)
    if len(relevant) < 2:
        return content
    return " ".join(f"({_format_timestamp(s['start'])}) {s['text']}" for s in relevant)

def _require_workspace_owner(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Owner only: deleting and granting tutor rights."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] != user_id:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace


def _require_workspace_manage(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allows owner or tutor, for everything that changes a course room."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_workspace_tutor(workspace["id"], user_id):
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

def _require_workspace_access(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allows owner or enrolled people, an inactive course room answers with 423."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_student_enrolled(workspace["id"], user_id):
        if not workspace.get("is_active", True) and not db.is_workspace_tutor(workspace["id"], user_id):
            raise HTTPException(status_code=423, detail=t("workspace.inactive", locale))
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

def _save_source_file_path(user_id: int, workspace_uuid: str, source_uuid: str, ext: str, local_path: str) -> str:
    """Stores an uploaded source, streaming from disk."""
    return save_aia_source_from_path(user_id, workspace_uuid, source_uuid, ext, local_path)

def _delete_workspace_files(workspace: dict) -> None:
    """Removes the course room folder as a whole, derived files included."""
    try:
        removed = delete_aia_workspace_folder(workspace["user_id"], workspace["uuid"])
        logger.info("KI Tutor: removed {} files for workspace {}", removed, workspace["uuid"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete files for workspace {}: {}", workspace["uuid"], e)

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

def _context_snippet(page_text: str, term: str, max_chars: int = 700) -> str:
    """A short excerpt of the page around the marked term."""
    text = re.sub(r"\s+", " ", (page_text or "")).strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    low = text.lower()
    pos = low.find((term or "").lower().strip()) if term else -1
    if pos < 0:
        head = text[:max_chars].rsplit(" ", 1)[0]
        return head + " …"
    half = max_chars // 2
    start = max(0, pos - half)
    end = min(len(text), pos + len(term) + half)
    if start > 0:
        start = text.find(" ", start) + 1 or start
    if end < len(text):
        cut = text.rfind(" ", start, end)
        if cut > start:
            end = cut
    snippet = text[start:end].strip()
    return ("… " if start > 0 else "") + snippet + (" …" if end < len(text) else "")


def _term_appears_in_text(term: str, text_lower: str) -> bool:
    """Checks whether the term appears verbatim or as a word stem in the text."""
    t = term.lower().strip()
    if not t:
        return False
    if t in text_lower:
        return True
    stem_len = max(5, len(t) * 3 // 4)
    stem = t[:stem_len]
    return bool(re.search(r"\b" + re.escape(stem), text_lower))


# A line already has evidence when it ends with a chip.
_HAS_CITE = re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*\|?\s*$")
