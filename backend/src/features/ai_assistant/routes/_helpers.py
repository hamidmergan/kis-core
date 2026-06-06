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


def _pick_attribution(hits: list[dict], max_distance: float) -> Optional[dict]:
    """Return the closest hit (min cosine ``vec_distance``) iff within the gate, else
    None. None == the line is not clearly in the sources -> no chip is attached.

    A table-of-contents / index chunk is never a target: it carries every topic keyword
    verbatim, so it can rank close, but citing the index page is always wrong."""
    cand = [h for h in hits
            if h.get("vec_distance") is not None and not _is_toc_chunk(h.get("content") or "")]
    if not cand:
        return None
    best = min(cand, key=lambda h: h["vec_distance"])
    return best if best["vec_distance"] <= max_distance else None


def _attribution_chip(qnum: int, chunk: dict, line: str) -> list[str]:
    """Nav-only citation chip for a post-hoc attributed line: page (PDF) or the chunk's
    start timestamp (media). No span offset, no keyword — clicking only scrolls to the
    page/timestamp. `line` kept in the signature for stability/logging."""
    page = chunk.get("page_number")
    if page is None:
        st = chunk.get("start_time")
        return [f"[{qnum}, {_format_timestamp(st)}]"] if st is not None else []
    return [f"[{qnum}, S. {page}]"]


def _needs_attribution(line: str) -> bool:
    """Whether a GENERIC answer line gets post-hoc attribution: substantial enough AND
    not already cited. Exposed so the caller can pre-collect the exact same candidate
    lines and embed them in ONE batch call (instead of one embed per line)."""
    return (len(_line_dedup_key(line)) >= _DEDUP_MIN_KEY_LEN
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


def _attribute_generic_text(text: str, search_one, source_id_to_qnum: dict, offset_fn=None, *,
                            seen_pages_by_source=None,
                            max_distance: float = _GENERIC_ATTRIB_MAX_DIST) -> str:
    """Re-ground each substantial, uncited line of a GENERIC answer via semantic search.

    ``search_one(line)`` returns ranked hits (dicts with vec_distance / source_id /
    page_number / content / optional start_time). ``offset_fn`` is accepted for
    backwards-compatibility but is now IGNORED — all chips are nav-only.
    Short/heading lines and lines that already carry a chip are left untouched;
    an unsupported line (gate) gets no chip.

    ``seen_pages_by_source`` (optional) maps source_id -> set of PDF page numbers that
    were actually retrieved into context. When given, a chip is only emitted if the
    attributed source/page was in that set (cross-check). Media sources (page_number is
    None) pass the check whenever their source_id is present in the mapping.

    The candidate gate is ``_needs_attribution`` — the caller uses the same predicate
    to batch-embed all candidate lines up front, so ``search_one`` only has to look up
    a precomputed vector here."""
    out: list[str] = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not _needs_attribution(line):
            out.append(line)
            continue
        # A table HEADER row (the next line is the |---| delimiter) is a column label,
        # not a claim — never cite it. (The delimiter row itself is skipped above: its
        # dedup key is empty.) Citing the header would also dirty the column titles.
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _is_table_row(line) and _is_table_delim(nxt):
            out.append(line)
            continue
        best = _pick_attribution(search_one(line) or [], max_distance)
        if best is not None and seen_pages_by_source is not None:
            pages = seen_pages_by_source.get(best["source_id"])
            if pages is None:
                best = None                                   # source never retrieved -> reject
            elif best.get("page_number") is not None and best["page_number"] not in pages:
                best = None                                   # PDF page not in retrieved set -> reject
            # media (page_number is None): empty/any set means the source WAS retrieved -> accept
        qnum = source_id_to_qnum.get(best["source_id"]) if best else None
        chips = _attribution_chip(qnum, best, line) if qnum else []
        # Table data row -> chip INSIDE the last cell (keeps GFM column count intact);
        # otherwise appended after the line.
        out.append(_place_chip(line, " ".join(chips)) if chips else line)
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
