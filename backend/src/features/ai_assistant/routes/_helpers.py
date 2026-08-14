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
from src.storage import (
    aia_transcript_key,
    delete_aia_workspace_folder,
    get_file,
    save_aia_source_from_path,
)

# Smaller models sometimes emit `[N] S. X` or `[N] MM:SS` (closing the bracket
# before the position label). Repair to `[N, S. X]` / `[N, MM:SS]` so the chip
# parser renders them as clickable citations.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")
_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")

# Lenticular brackets 【】 do not occur in real LATIN prose — only LLMs emit them there.
# The prompt forbids the model from citing sources at all (chips are attached post-hoc),
# yet some models (Qwen-family especially) still leak a bare 【source】 / 【Quelle】
# placeholder. A 【…】 with NO page ("S. 6") or timestamp ("08:58") locator inside is not
# a real citation: it renders as dead text AND survives the copy-strip. Drop it (with one
# leading space) before attribution runs. Valid 【1, S. 6】 / 【1, 08:58】 are kept by the
# negative lookahead. In CJK, though, 【】 ARE genuine punctuation, so a span whose
# content contains a CJK/Hangul/Kana character is kept as real prose (language-agnostic).
_STRAY_LENTICULAR_RE = re.compile(
    r"\s?【(?![^】]*(?:S\.\s*\d|\d{1,2}:\d{2}|[぀-鿿가-퟿]))[^】]*】"
)


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations and drop stray 【…】 placeholders."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    text = _STRAY_LENTICULAR_RE.sub("", text)
    return text


# Arrows as a connector between two steps ("Es wird zum Subjekt. → Es steht am
# Anfang."). The model reaches for them on its own — they are in neither the sources
# nor the prompt — and they are exactly wrong for a language learner: the arrow hides
# the verb and leaves the reader to guess it. Prompt rules did not hold, and every
# wording that did suppress them also weakened the not-in-sources refusal (measured
# 2026-07-29, three attempts), so this is enforced here instead of asked for there.
# Observed arrows always follow a finished sentence, so dropping the connector leaves
# clean prose. Runs per streamed token, hence a plain sub and no state.
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


# ── Path-based variants (low-RAM upload streaming) ───────────────────────────
# The byte-based helpers above keep their callers untouched. These operate on
# files on disk so a large upload never has to sit fully in memory: the request
# body is streamed to a temp file and only the path is passed around.

def _convert_office_to_pdf_path(src_path: str, ext: str, out_dir: str, locale: str = DEFAULT_LOCALE) -> str:
    """Convert a .docx/.pptx file on disk to PDF via LibreOffice. Returns the
    PDF path in ``out_dir``. Raises HTTPException on failure."""
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
    """Remux an MP4 on disk for progressive playback (moov atom up front).
    Returns the remuxed path, or the original ``src_path`` on any failure."""
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
    """Normalize text for verbatim keyword matching: NFKC, case-fold, unify the
    various Unicode hyphens (e.g. non-breaking U+2011 in 'Peer‑Review'), collapse
    whitespace. Makes the keyword-in-chunk check robust to cosmetic differences."""
    s = unicodedata.normalize("NFKC", s).casefold()
    for hy in ("‐", "‑", "‒", "–", "—", "−"):
        s = s.replace(hy, "-")
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


# A page ("S. 6" / "S.6") or timestamp ("08:58" / "1:05:19") locator, optional leading pipe.
_SRC_LOCATOR_RE = re.compile(r"\|?\s*(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)\s*", re.IGNORECASE)
_LIST_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _is_pure_source_ref(line: str, names: list[str]) -> bool:
    """True when a line is JUST a source reference — a known source filename plus a
    page/timestamp locator, e.g. ``- VL1.webm | 08:58`` or ``01_Intro.pdf | S. 6``.
    That is the model enumerating sources in prose, which the clickable nav chips
    already cover. A line with real prose around the filename (an inline mention like
    "laut 01_Intro.pdf auf Seite 6 …") is NOT flagged — after removing the filename and
    the locator, substantial words remain. Language-agnostic: keys on a known filename
    plus a locator, no per-language word list."""
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
    """Remove a model-written "sources" enumeration: a run of >=2 pure source-reference
    lines (:func:`_is_pure_source_ref`) plus a short heading line right above it (one
    that ends with ':' — "Quellen:", "Sources:", any language). The nav chips already
    list every source/page, so this textual copy is pure noise. Single inline mentions
    are untouched (the >=2 run requirement); a lone heading without a list is kept."""
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
    """Drop a GFM table that has fewer than 2 data rows — a one-row "table" that should
    have been a sentence (the model duplicating a single fact as BOTH prose and a
    table). Only stripped when substantial non-table text remains, so a legitimate
    stand-alone single-row table (the whole answer) is kept rather than silently lost."""
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
# An ADDITIONAL chip from the SAME source is only added when its chunk sits CLOSE to the
# block's best chunk — within this distance delta. A relative gate, not just the absolute
# 0.6: otherwise a clearly-best passage (e.g. 0.21) collects spurious near-misses (0.32)
# that are on-topic enough to pass 0.6 but are not where the claim actually came from.
# Genuine co-sources within one document (a fact stated on two pages / in two laws) sit at
# ~equal distance and stay.
#
# It does NOT gate a chunk from ANOTHER source. A workspace typically holds the slides AND
# the recording of the same session, so most statements exist twice, once written and once
# spoken — and those two never land at the same distance, because talking around a fact at
# length is what embeddings reward. Measured: a deadline stated at 08:58 in the talk (0.31)
# and on the slide (0.47) lost the slide to this gate, and the literal-evidence exemption
# could not save it either — the words the two share ("Abgabe", "Hausarbeit") are the words
# the whole course carries, so rarity never calls them distinctive. One reader wants the
# slide, another wants to hear the passage; that is the same rule _extra_chip_earns_place
# already applies on the clause path, now applied here too.
_MULTI_CHIP_MAX_DELTA = 0.08
# Clause coverage: a multi-fact unit is also attributed fact-by-fact, so ONE chip stop may
# carry up to this many chips total (unit-level chips PLUS one per distinct clause source).
# In prose a chip stop is a SENTENCE, so this is the per-sentence ceiling. Matches the
# frontend's per-group cap: one visible chip plus two behind the caret.
_COVERAGE_MAX_CHIPS_PER_LINE = 3
# How many looked-up chunks may jump the queue for one line. Beyond a handful they stop
# being evidence and start being a second search.
_MAX_LITERAL_CANDIDATES = 4
# A line whose embedding is within this cosine distance of a canonical no-info SENTINEL is
# an honest "the answer is not in the sources" refusal, NOT a claim — it must get NO chip,
# even inside an otherwise-grounded COMPOUND answer (one sub-question answered, another
# refused). Distance alone cannot separate this from a real-but-vague claim (both sit in the
# 0.6-0.85 guarantee band), so a refusal is detected by meaning, not by its chunk distance.
# Language-agnostic: the model writes the refusal in the QUESTION's language and a
# multilingual embedding places that translation near the de/en sentinel — no word lists.
# Calibrated against the live embedding model: across refusal paraphrases (de + en, incl. the
# topic-padded "Informationen darüber, welches Gesetz …, sind nicht enthalten") the distance
# to the nearest sentinel stayed <=0.48, while real factual answer lines were >=0.75 — a wide,
# clean gap. The gate sits in the MIDDLE of that gap, not on its edge: 0.40 sat right on a
# refusal at 0.389 and so fired only intermittently as the wording shifted.
_REFUSAL_MAX_DIST = 0.60


def _cos_dist(a, b) -> float:
    """Cosine distance (1 - cosine similarity) between two equal-length vectors. Returns the
    max distance 1.0 if either vector is degenerate (zero norm) so a bad embed never
    falsely flags a line as a refusal."""
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
    """Subset of candidate lines that are a "not in the sources" refusal, by embedding
    proximity to the canonical no-info ``sentinel_vecs`` (see ``RAG_NO_INFO_SENTINEL``).

    Caller embeds the candidate lines AND the sentinels in one batch, then passes the
    resulting set to ``_attribute_generic_text`` so those lines are skipped during
    attribution. Empty ``sentinel_vecs`` (e.g. the embed batch failed) -> empty set, i.e.
    the filter is simply off and behaviour falls back to the distance-only path."""
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
    """True if the WHOLE answer is a "not in the sources" refusal, by embedding proximity
    to a canonical no-info ``sentinel`` (see ``RAG_NO_INFO_SENTINEL``).

    Mirrors ``_refusal_lines`` but for a single complete answer instead of per-line, used by
    the single-page-scope path: that path appends ONE nav anchor without running per-line
    attribution, so it would otherwise anchor an honest refusal to the scoped page. Language-
    agnostic: the model writes the refusal in the question's language and a multilingual
    embedding places it near the de/en sentinel — no word lists. Any embed failure → False
    (anchor stays), so a transient error never silently strips a legitimate citation."""
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


def _scope_chunk_ids(scope_chunks: Optional[list[dict]]) -> Optional[set]:
    """The set of chunk ids the model was shown for an EXPLICIT page/time scope.

    Returned to attribution as a clamp: a citation may only point at a chunk INSIDE the
    scoped window. For media this is the load-bearing fix — a media chunk's seen-check is
    source-level (any chunk of the source passes ``_is_seen``), so without this clamp a
    "from minute 40" summary could be attributed to a closer chunk at minute 13. ``None``
    means no scope / no restriction; an empty scope never yields an empty set (which would
    strip every chip) — it falls back to ``None``."""
    if not scope_chunks:
        return None
    ids = {c["id"] for c in scope_chunks if c.get("id") is not None}
    return ids or None


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


# A line wrapped ENTIRELY in bold, optionally followed by sentence punctuation:
# ``**Überblick**``, ``**Was ist Literaturrecherche**?``. The inner text may not contain a
# second emphasis run, so ``**A** und **B**`` (two emphasised words in one sentence) does
# NOT match. Anchored at both ends, so a bullet ("- **Zitat.**") is not a heading either.
_BOLD_HEADING_RE = re.compile(r"^(\*\*|__)(?:(?!\1).)+\1[\s.?!:]*$")


def _is_heading_line(line: str) -> bool:
    """A section TITLE, in either shape the model writes: a markdown ``## Tipps für die
    Suche`` or a line set entirely in bold (``**Was ist Literaturrecherche**?``).

    A title names what follows, it does not assert anything, so it must never carry a
    citation chip — the chip would point at a page that backs nothing the title says, and
    it lands right in the middle of the heading. The restated question at the top of an
    answer is the worst case of this.

    Both shapes are treated the same everywhere: own attribution block, no chip, never a
    continuation of the paragraph above. Shape-only, no word lists → holds in every answer
    language."""
    return line.lstrip().startswith("#") or bool(_BOLD_HEADING_RE.match(line.strip()))


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
            and not _is_heading_line(line)
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


def _attach_chips(text: str, chip_str: str) -> str:
    """Attach ``chip_str`` BEFORE the sentence-ending punctuation when the
    text ends in a plain '.', '!' or '?', so ``Satz.`` -> ``Satz [chip].``. If the text does
    NOT end in bare terminal punctuation (a trailing '**' emphasis marker, a closing quote, a
    table pipe, or no punctuation at all), the chip is simply appended — never inserted into
    markup. Language-agnostic; keys only on the trailing character(s)."""
    s = text.rstrip()
    i = len(s)
    while i > 0 and s[i - 1] in ".!?":
        i -= 1
    if 0 < i < len(s):                     # a real terminal-punctuation run with text before it
        return f"{s[:i].rstrip()} {chip_str}{s[i:]}"
    return f"{s} {chip_str}"


def _place_chip(line: str, chip_str: str) -> str:
    """Attach ``chip_str`` to a line. For a table row the chip goes INSIDE the last
    cell (before the closing pipe) so the row keeps its pipe-defined column count and
    GFM still parses the block as a table; otherwise it is attached via :func:`_attach_chips`
    (before the sentence-ending period)."""
    if _is_table_row(line):
        return re.sub(r"\s*\|\s*$", f" {chip_str} |", line.rstrip())
    return _attach_chips(line, chip_str)


def _in_scope(chunk: dict, scope_ids: Optional[set]) -> bool:
    """True if the chunk is inside the explicit scope window (or no scope is active).

    ``scope_ids`` (from :func:`_scope_chunk_ids`) is the set of chunk ids the model was
    actually shown; ``None`` means no scope, so everything passes."""
    return scope_ids is None or chunk.get("id") in scope_ids


# Comma/semicolon only — NOT colon: a colon would split clock times ("14:53") and ratios in
# prose into junk fragments, and the comma already separates list items.
# Content words for the coverage check: 4+ characters, case-folded. The length floor drops
# function words (der/die/und, the/and/of) WITHOUT a per-language stop list, so this holds in
# every answer language — the same shape-only rule the rest of attribution follows.
_CONTENT_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _content_words(text: str) -> set:
    return {w.casefold() for w in _CONTENT_WORD_RE.findall(text or "")}


def _extra_chip_earns_place(unit: str, primary: dict, extra: dict) -> bool:
    """Whether an ADDITIONAL chip earns its place next to the closest one.

    Two different rules, because "adds nothing" means different things across and within a
    document:

    - A DIFFERENT source always earns it, even for the very same fact. A workspace typically
      holds the slides AND the recording of the same session, so most statements exist twice,
      once written and once spoken. That is a second way in, not noise: one reader wants the
      slide, another wants to hear the passage.
    - A second passage of the SAME source has to cover a content word OF THE UNIT that the
      closest passage does not already carry. A clause search always returns its nearest
      chunk, even when the clause is not a fact of its own ("inklusive Abbildungen und
      Tabellen"). Measured live, 7 of 13 extra chips cited a passage covering NO word the
      first was missing — near misses, not co-sources. Overlap between the two passages
      cannot catch this: they ARE different (mean overlap 0.17), just about something else.

    Word sets only (4+ characters, case-folded), so no per-language stop list is involved."""
    if primary.get("source_id") != extra.get("source_id"):
        return True
    unit_words = _content_words(unit)
    if not unit_words:
        return True
    new_words = unit_words & _content_words(extra.get("content") or "")
    return bool(new_words - _content_words(primary.get("content") or ""))


_CLAUSE_SPLIT_RE = re.compile(r"[,;]")


def _clauses(line: str) -> list[str]:
    """Substantial sub-clauses of a line (comma/semicolon-separated), EXCLUDING the
    whole line. A multi-fact sentence ("X von sechs Seiten, sowie eine Praesentation") is
    attributed fact-by-fact: each clause is embedded and searched on its OWN focused vector,
    so a fact whose source segment sits far from the diluted whole-sentence vector still
    earns a chip instead of being trimmed by the cap / relative-delta gate.

    Punctuation-only split keeps this language-agnostic (no conjunction word lists). A clause
    is kept only if it is substantial on its own (same dedup-key length floor as a line), so
    short fragments ("sowie", "z. B.") never become spurious queries. The leading clause may
    still carry the markdown bullet prefix — harmless for embedding and substring search."""
    if not _CLAUSE_SPLIT_RE.search(line):
        return []
    whole = line.strip()
    out: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(line):
        p = part.strip()
        if p and p != whole and len(_line_dedup_key(p)) >= _DEDUP_MIN_KEY_LEN and p not in out:
            out.append(p)
    return out


# A sentence boundary: one or more terminal marks, whitespace, then a word char. The
# lookahead is NOT consumed, so the following letter's case is checked in code (only an
# UPPERCASE start is a boundary — a lowercase start is a wrapped/continued clause). A mark
# directly before a DIGIT (a decimal "6.2", a "S. 5" page ref) never matches, since the
# lookahead excludes digits — decimals need no separate guard.
_SENT_BOUNDARY_RE = re.compile(r"[.!?]+\s+(?=[^\W\d_])")


def _is_abbreviation_end(prefix: str) -> bool:
    """Whether the terminal ``.`` of ``prefix`` closes an abbreviation / number rather than a
    sentence — i.e. a split here would drop a chip mid-sentence. Language-agnostic (NO word
    lists), keyed only on the shape of the last whitespace-token before the mark:

    - a single char ("z. B.", "S.", an initial),
    - a bare number ("am 3. Juli", an ordinal — favoured over the rare "… Seite 5. Der …",
      which is locally identical and only costs a missed split),
    - a short dotted token ("u.a.", "d.h.", "e.g.", "i.e." — internal '.' and <= 4 chars, so
      a real domain "th-luebeck.de" is NOT caught and the sentence-ending '.' after an email
      still splits),
    - a short Capitalised token ("Prof.", "Dr.", "Nr.", "Abb.", "Hrsg." — <= 4 chars).

    Bias is PRECISION: each rule suppresses an ambiguous split. A missed split merely merges
    two sentences under one chip (the old block behaviour); a false split cannot happen."""
    tok = prefix.rstrip(".!?").split()
    if not tok:
        return False
    # Strip surrounding brackets/quotes/dashes so an opening "(" or a quote does not hide the
    # abbreviation inside it ("(z. B. …)", "„z. B."). Internal dots (u.a.) are kept.
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
    """Split prose ``text`` into sentences for per-sentence citation attribution.

    Used only on PROSE blocks (bullets/tables/headings keep their chip at the unit end).
    Splits at :data:`_SENT_BOUNDARY_RE` boundaries that :func:`_is_abbreviation_end` does not
    veto. Precision over recall: a MISSED split just leaves two sentences sharing one chip (no
    regression), a FALSE split would strand a chip inside a sentence. Returns trimmed
    sentences (each incl. its terminal mark); a single ``" ".join`` reconstructs the prose."""
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
    """Chunks that carry a distinctive FIGURE of ``line`` verbatim, looked up in the material.

    Ranking by meaning cannot reach these. For "mittwochs von 17:30 bis 18:30 Uhr" the one
    slide stating that time sat at distance 0.656 — outside the citation gate entirely —
    while three passages that merely mention office hours filled all three chip slots. No
    ordering rule fixes a candidate that was never a candidate; the figure has to be looked
    up. Which figures qualify is decided in aia_literal_evidence (structured and rare only).

    The usual gates still apply: a looked-up chunk must have been in the model's context
    and inside any explicit page/time scope, or it is dropped like any other.
    """
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
            # The RAREST match wins: a date recurring on four pages says far less about
            # where a claim comes from than a time standing in exactly one place. Without
            # this ordering the four hits for "22.04.2026" filled the chip slots and the
            # single hit for "18:30" — the only passage stating the office hour — was
            # pushed out again.
            if cid not in best or len(hits) < best[cid][0]:
                best[cid] = (len(hits), dict(h))
    ordered = sorted(best.values(), key=lambda pair: pair[0])
    return [h for _, h in ordered][:_MAX_LITERAL_CANDIDATES]


def _line_candidates(line: str, search_one, context_chunks: Optional[list[dict]],
                     seen_pages_by_source: Optional[dict],
                     scope_ids: Optional[set] = None,
                     literal_lookup=None, corpus: Optional[list[str]] = None) -> list[dict]:
    """Retrieved (seen), non-TOC source chunks that could ground ``line``, closest-first.

    If an EXACT verbatim chunk exists (a name/email/number we already retrieved, whose
    page we know), it is the SOLE high-confidence candidate — semantic near-misses on
    other pages are suppressed. Otherwise the seen semantic hits, sorted by distance: a
    reworded/synthesised line may legitimately draw from several passages, so the caller
    can attach a chip per distinct source/page.

    ``scope_ids`` clamps candidates to an EXPLICIT page/time scope: a "from minute 40"
    summary may only cite chunks inside that window, never a closer chunk from minute 13."""
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
    # A chunk that states the line's figure moves right BEHIND the closest one. The closest
    # stays the anchor of the relative gate, but the passage carrying the claim is now
    # considered before the merely-nearby ones. Ordering is the load-bearing part: the
    # slide with the office hour's time WAS among the candidates, at rank eight, and the
    # three chip slots were long full — being allowed in is worth nothing if nobody looks.
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
                    line: str = "", corpus: Optional[list[str]] = None) -> list[str]:
    """Build the chip list for ONE line from its closest-first candidates.

    The first usable candidate is the GUARANTEE chip (closest retrieved chunk, accepted
    up to ``guarantee_dist`` so a grounded claim is never left chip-less); each further
    chip must be a DISTINCT source/page within the normal ``max_distance`` (a genuine
    additional contributing passage), capped at ``_MAX_CHIPS_PER_LINE``. A passage from
    ANOTHER source needs only that absolute gate — the relative ``_MULTI_CHIP_MAX_DELTA``
    sorts near-misses out within one document and has nothing to say across two. Overview mode
    passes ``guarantee_dist = max_distance`` so a loose, misleading single chip on a
    many-source synthesis line is dropped instead of guaranteed.

    Past the relative gate one thing still earns a chip: stating the claim WORD FOR WORD
    where the closest passage does not (``line`` given; see aia_literal_evidence). The
    gate ranks by distance alone, and a transcript segment talking around a fact reliably
    beats the slide that states it — measured 0.394 against 0.501 for an office hour whose
    time only the slide carries. The absolute ``max_distance`` still applies, so this
    widens what may be cited, never how far.

    ``corpus`` is what "word for word" is judged against: every chunk the answer was
    written from. Falling back to this line's own candidates makes the sample too small
    to separate a filler adverb from a technical term."""
    from src.services.aia_literal_evidence import adds_literal_evidence
    chips: list[str] = []
    keys: set = set()
    primary_d: Optional[float] = None
    primary_content = ""
    primary_source = None
    evidence_corpus = corpus or [c.get("content") or "" for c in cands]
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
            primary_source = h.get("source_id")
        elif h.get("literal"):
            pass                         # states the claim's figure verbatim: it IS the source
        elif d > max_distance:
            break                        # off topic for everyone, evidence or not
        elif h.get("source_id") != primary_source:
            pass                         # another document: a second way in, not a near-miss
        elif d > primary_d + _MULTI_CHIP_MAX_DELTA and not (
                line and adds_literal_evidence(
                    line, h.get("content") or "", primary_content, evidence_corpus)):
            continue                     # further away AND adds nothing the best one lacks
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
    if _is_heading_line(line):
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
    """A plain PROSE paragraph line — NOT a list item, heading, or table row/delimiter.

    Only prose lines get per-sentence citation chips; bullets and table
    rows keep their single end-of-unit chip. Mirrors the exclusions in :func:`_is_continuation`
    so the two agree on what counts as a bullet/heading. Language-agnostic (structure only)."""
    ls = line.lstrip()
    if not ls.strip() or _is_table_row(line) or _is_table_delim(line):
        return False
    if _is_heading_line(line):
        return False
    if re.match(r"[-*+]\s", ls) or re.match(r"\d+[.)]\s", ls):
        return False
    return True


def _holds_for_every_sentence(text: str, predicate) -> bool:
    """Whether ``predicate`` holds for EVERY sentence of ``text``.

    The overview suppressors (:func:`_names_many_laws`, :func:`_enum_chip_unbacked`) exist to
    stop ONE chip being glued to a unit that enumerates many sources, and they were
    calibrated when a unit meant one sentence. A BLOCK can be several sentences (a
    multi-sentence bullet), where a single parenthetical ("(AND, OR, NOT)") or one example
    list would strip the chip off everything around it.

    So on the block path they are judged sentence by sentence and only silence the block when
    they hold throughout — for a genuine enumeration (one sentence, or a block that is nothing
    but enumerations) the outcome is exactly as before. The prose path already judges each
    sentence on its own and needs no wrapper."""
    sents = _split_sentences(text) or [text]
    return all(predicate(s) for s in sents)


def _attribution_subunits(line: str) -> list[str]:
    """Sub-line text units to pre-embed alongside a candidate ``line``, so ``search_one``
    reuses a batched vector instead of one embed call PER unit (which would hammer the
    shared rate limit). Mirrors EXACTLY what attribution searches below the line level:

    - a PROSE paragraph of > 1 sentence is attributed per sentence, so return each sentence
      AND each sentence's clauses (what :func:`_attribute_prose_line` searches),
    - any other line (bullet, table row, single-sentence prose) is attributed as ONE unit,
      so return its clauses (what the block path searches).

    Order preserved, de-duplicated; the whole line is never returned (the caller always
    embeds it as a candidate on its own)."""
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


def _attribute_prose_line(sentences: list[str], search_one, source_id_to_qnum: dict, *,
                          context_chunks, seen_pages_by_source, scope_ids,
                          max_distance: float, guarantee: float, overview: bool,
                          literal_lookup=None) -> str:
    """Rebuild a PROSE paragraph with a citation chip AFTER EACH sentence.

    Each sentence is grounded on its OWN vector — whole-sentence closest source plus one
    coverage chip per distinct clause — reusing the exact block-path selector and gate
    (:func:`_line_candidates`, :func:`_chips_for_line`). A sentence with no close, seen
    source stays chip-less, exactly like an unsupported block. Overview suppressions apply
    per sentence: a many-law synthesis or an unbacked spelled-out enumeration gets no chip.
    Called ONLY for a grounded answer's single-line prose block, so ``guarantee`` is already
    resolved by the caller (loose for SPECIFIC, tight = ``max_distance`` for overview)."""
    corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    parts: list[str] = []
    for sent in sentences:
        chips: list[str] = []
        if _needs_attribution(sent) and not (overview and _names_many_laws(sent)):
            cands = _line_candidates(sent, search_one, context_chunks,
                                     seen_pages_by_source, scope_ids,
                                     literal_lookup=literal_lookup, corpus=corpus)
            if cands and not (overview and _enum_chip_unbacked(sent, cands[0].get("content") or "")):
                chips = _chips_for_line(cands, source_id_to_qnum, max_distance,
                                        guarantee_dist=guarantee, line=sent, corpus=corpus)
                seen_targets = set(chips)
                for cl in _clauses(sent):
                    ccands = _line_candidates(cl, search_one, context_chunks,
                                              seen_pages_by_source, scope_ids,
                                              literal_lookup=literal_lookup, corpus=corpus)
                    cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                             guarantee_dist=guarantee, line=cl,
                                             corpus=corpus) if ccands else []
                    # A clause search ALWAYS returns its nearest chunk, so an extra chip must
                    # earn its place: it only stays if its passage covers a word of the
                    # SENTENCE the closest passage is missing.
                    if (cchips and cchips[0] not in seen_targets
                            and _extra_chip_earns_place(sent, cands[0], ccands[0])):
                        chips.append(cchips[0])
                        seen_targets.add(cchips[0])
                        if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                            break
        parts.append(_attach_chips(sent, " ".join(chips)) if chips else sent)
    return " ".join(parts)


# Post-hoc attribution searches LOCAL Postgres once per sentence/clause. Done serially that
# is the dominant cost of the after-answer pause (~13.7s of ~15.3s measured). The pool is a
# ThreadedConnectionPool(1, 20), so we fan the searches across a thread pool and keep the
# sequential attribution walk a pure dict lookup. 8 leaves ample pool headroom for other
# requests and stays sane on the 4-core prod box (the queries are partly I/O-bound).
_ATTRIB_SEARCH_CONCURRENCY = 8


def _parallel_search(lines: list[str], search_fn: Callable[[str], list],
                     max_workers: int = _ATTRIB_SEARCH_CONCURRENCY) -> dict[str, list]:
    """Run ``search_fn`` once per UNIQUE non-blank line across a thread pool.

    Returns ``{line: hits}`` the sequential attribution walk then looks up instead of
    hitting the DB inline. Correctness is identical to calling ``search_fn(line)`` inline:
    the map holds exactly that result per line, deduped so a repeated line is searched once.
    A search that raises maps to ``[]`` (same as the caller's own guarded search), so one
    bad line never sinks the batch."""
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
    """Warm the post-hoc attribution caches WHILE the answer is still streaming, so the
    after-answer pause shrinks toward zero.

    The stream calls :meth:`feed_line` with each COMPLETED answer line as it arrives; a
    candidate line (``_needs_attribution``) and its sentence/clause sub-units
    (``_attribution_subunits`` — exactly what attribution later searches) are queued,
    deduped by exact text. A background pump calls :meth:`flush`, which embeds the queued
    batch in ONE provider call and parallel-searches it, filling ``vecs`` and ``hits``.
    Attribution then reads those caches and only computes the misses.

    Rate-limit safe: a single flush runs at a time (``_lock``), so bursts coalesce into a
    few batched embed calls rather than one-per-line — the shared 2/s embed budget holds.
    Correctness safe: everything is keyed by exact text and a miss is just recomputed
    inline at attribution, so a failed or stale prewarm can never change the answer."""

    def __init__(self, embed_batch: Callable[[list], list],
                 search_with_vec: Callable[[str, Optional[list]], list]):
        # embed_batch: (list[str]) -> list[vector]  (ONE call for the whole batch)
        # search_with_vec: (line, vector|None) -> list[hit dicts]  (the same search
        #   attribution does, given a precomputed vector)
        self._embed_batch = embed_batch
        self._search_with_vec = search_with_vec
        self.vecs: dict[str, list] = {}
        self.hits: dict[str, list] = {}
        self.flushes = 0            # embed calls actually spent (visibility for the rate budget)
        self._seen: set[str] = set()
        self._pending: list[str] = []
        self._lock = asyncio.Lock()

    def feed_line(self, line: str) -> None:
        """Queue a completed answer line and its sub-units for prewarming, if it is a
        candidate. No-op for headings/labels/blank/already-seen text."""
        if not line or not _needs_attribution(line):
            return
        for unit in [line, *_attribution_subunits(line)]:
            if unit and unit.strip() and unit not in self._seen:
                self._seen.add(unit)
                self._pending.append(unit)

    def pending_count(self) -> int:
        return len(self._pending)

    async def flush(self) -> None:
        """Embed + parallel-search whatever is queued (one batch), into ``vecs``/``hits``.
        Single in-flight; a concurrent call finds the queue already drained and no-ops."""
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
                            literal_lookup=None) -> str:
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
    "not in the sources" answer never does, so it stays uncited as before.

    ``refusal_lines`` (optional) is the set of answer lines the caller identified as a
    "not in the sources" REFUSAL (embedding-near the no-info sentinel). They are skipped
    here exactly like a non-candidate line, so a COMPOUND answer that answers one part and
    refuses another never attaches a (misleading) source chip to the refusal sentence — the
    GUARANTEE would otherwise chip it, since the answered part already grounded the whole."""
    lines = text.split("\n")
    # An explicit page/time scope clamps attribution to the chunks the model was shown, so
    # a "from minute 40" summary can never cite a closer chunk from minute 13 (media's
    # seen-check is source-level and would otherwise let it through).
    scope_ids = _scope_chunk_ids(scope_chunks)
    # What "states it word for word" is judged against: everything the answer was written
    # from, so a filler adverb cannot pass for a distinctive term (see aia_literal_evidence).
    evidence_corpus = [c.get("content") or "" for c in (context_chunks or [])] or None
    # Pass 1: gather seen candidates per substantial line; decide if the answer is grounded.
    # Also gather per-CLAUSE candidates so a multi-fact line can be attributed fact-by-fact
    # in Pass 2.
    cand_by_idx: dict[int, list[dict]] = {}
    clause_cands_by_idx: dict[int, list[list[dict]]] = {}
    grounded = False
    for i, line in enumerate(lines):
        if not _needs_attribution(line):
            continue
        # A "not in the sources" refusal sentence is not a claim — never attribute it (it
        # neither grounds the answer nor earns a chip), even when another line is grounded.
        if refusal_lines and line in refusal_lines:
            continue
        # A table HEADER row (next line is the |---| delimiter) is a column label, not a
        # claim — never cite it (citing it would also dirty the column titles).
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
        # Chips are NOT deduped across blocks. Two DISTINCT claims may legitimately draw on
        # the same passage (a "theory" bullet and a "practice" bullet both grounded in the
        # one segment that contrasts them), so each block must keep its OWN closest source(s)
        # — even one an earlier block already cited. Cross-block dedup used to hand a shared
        # best source to the first block and leave the later, distinct claim with only a far,
        # wrong leftover. Genuine restatements (a fact repeated in two shapes) are collapsed
        # upstream — duplicate lines by _dedup_repeated_lines, redundant one-row tables /
        # model source-lists by answer-cleanup — so a citation is never sacrificed for tidiness.
        for blk in _attr_blocks(lines):
            # Per-sentence chips for a PROSE block — a block whose FIRST line
            # is prose (not a bullet, heading, or table row). EACH line's sentences get their
            # OWN chip after the sentence, so a two-line intro ("**Überblick**\n<prose>") or a
            # multi-sentence paragraph is chipped sentence-by-sentence, not once at the end.
            # Bullets and table rows keep the aggregating block path below. A refusal line
            # carries no candidates from Pass 1 and is left verbatim here.
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
                            literal_lookup=literal_lookup)
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
            # Overview: a spelled-out name-list whose cited chunk backs only one item is the
            # misleading "one chip on a many-source enumeration" case → leave it chip-free.
            # Content-gated so an in-source example list (chunk holds all items) keeps its chip.
            _cited = agg[0].get("content") or ""
            if overview and _holds_for_every_sentence(
                    block_text, lambda s: _enum_chip_unbacked(s, _cited)):
                continue
            chips = _chips_for_line(agg, source_id_to_qnum, max_distance,
                                    guarantee_dist=guarantee, line=block_text,
                                    corpus=evidence_corpus)
            # Clause coverage: the whole-line vector is closest to ONE fact, so the cap /
            # relative-delta gate trims the others. Add each distinct clause's single closest
            # in-gate source as a coverage chip — so every fact in a multi-fact bullet earns a
            # link — deduped against what the line already shows and bounded by
            # _COVERAGE_MAX_CHIPS_PER_LINE. A table data row keeps its in-cell chip only.
            if not _is_table_row(lines[blk[-1]]):
                seen_targets = set(chips)
                for idx in blk:
                    for ccands in clause_cands_by_idx.get(idx, []):
                        cchips = _chips_for_line(ccands, source_id_to_qnum, max_distance,
                                                 guarantee_dist=guarantee, line=block_text,
                                                 corpus=evidence_corpus)
                        # Same rule as the prose path: an extra chip must cover something of
                        # the BLOCK that the closest passage does not already carry.
                        if (cchips and cchips[0] not in seen_targets
                                and _extra_chip_earns_place(block_text, agg[0], ccands[0])):
                            chips.append(cchips[0])
                            seen_targets.add(cchips[0])
                            if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                                break
                    if len(chips) >= _COVERAGE_MAX_CHIPS_PER_LINE:
                        break
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

def _require_workspace_owner(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Owner only. The two things a tutor must not do.

    Deleting the workspace is unrecoverable, and handing out tutor rights would
    let the circle of people with full rights grow without the owner noticing.
    Inviting learners is not in here: that is ordinary tutoring work and cannot
    hurt anything.
    """
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] != user_id:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace


def _require_workspace_manage(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    """Allow the owner OR a tutor. Used for everything that changes a workspace.

    A tutor joined through a tutor link and manages the workspace on the owner's
    behalf, with the same rights. The system role (staff/admin/user) never grants
    this, only ownership or a tutor enrollment does.
    """
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] == user_id:
        return workspace
    if db.is_workspace_tutor(workspace["id"], user_id):
        return workspace
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

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

def _save_source_file_path(user_id: int, workspace_uuid: str, source_uuid: str, ext: str, local_path: str) -> str:
    """Store an uploaded source, streaming from a file on disk (low-RAM).

    Returns the stored key (S3) or absolute path (local)."""
    return save_aia_source_from_path(user_id, workspace_uuid, source_uuid, ext, local_path)

def _delete_workspace_files(workspace: dict) -> None:
    """Remove the workspace folder as a whole.

    Per-source deletion would leave the derived artifacts (transcript,
    subtitles) behind, and those hold the full text of a lecture recording.
    """
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
    """A short excerpt of ``page_text`` centred on the marked ``term``, for grounding
    a glossary definition in how the term is actually used in the document.

    Finds the first case-insensitive occurrence of the term and returns a window of
    at most ``max_chars`` around it, trimmed at whitespace so words are not cut mid-way
    (an ellipsis marks a trimmed edge). If the term is not found literally (an inflected
    or multi-word mark), the leading ``max_chars`` of the page are returned instead, so
    there is always *some* context. Empty input → "". Pure so it is unit-testable without
    the route's DB/LLM dependencies."""
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


# A line "already has a citation" if it ends with a chip token — optionally followed
# by a markdown table cell's closing pipe (the chip can sit inside the last cell).
_HAS_CITE = re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*\|?\s*$")
