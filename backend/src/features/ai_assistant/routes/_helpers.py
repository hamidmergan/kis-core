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


# ─── Citation page/timestamp resolution ─────────────────────────────────────
# The LLM types a page/timestamp as free text and routinely hallucinates it
# (e.g. "S. 44" on a 10-page PDF). We never trust that number. Instead we
# re-derive the real position from the verbatim keyword the citation carries,
# matched against the actual chunk content the model was given. A citation that
# cannot be grounded to a real position is dropped - better no chip than a
# fabricated one. Image pages without a text layer survive as long as the cited
# page actually exists in the source (keyword just can't be matched there).

# Capturing variant of the frontend citation grammar:
#   group1 = source number N (optional), group2 = page, group3 = timestamp,
#   group4 = keyword section. Accepts CJK lenticular brackets like the frontend.
#   The page form also tolerates a range like "S. 6-7" (any Unicode hyphen): the
#   model occasionally mimics a section marker it saw in the content. We capture
#   the FIRST page and swallow the rest, so the whole bracket still resolves to a
#   clean single-page chip instead of leaking through as broken raw text.
_CITE_RESOLVE_RE = re.compile(
    r"[\[【]\s*(?:Q?(\d+)\s*,\s*)?"
    r"(?:S\.\s*(\d+)(?:\s*[-‐‑‒–—−]\s*\d+)?(?:\s*@\d+-\d+)?|(\d{1,2}:\d{2}(?::\d{2})?))"
    r"\s*(?:[|❘]\s*([^\]】]+?))?\s*[\]】]"
)


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
# so a normal 3-dot ellipsis is NOT caught) followed by a page-reference number. Such
# a line carries the topic keyword verbatim ("Vektorgrafik ........ 4"), so a claim
# about that topic would wrongly ground to the index page instead of the real content
# section. Structure-only -> language-agnostic (KIS is multi-tenant). Limitation:
# leaders that aren't solid ASCII dots (spaced dots, whitespace alignment) aren't caught.
_TOC_LEADER_RE = re.compile(r"\.{4,}\s*\d{1,4}")


def _strip_toc_lines(text: str) -> str:
    """Drop lines that are table-of-contents / index entries (dotted leader + page
    number). Works per line, so genuine prose on the same chunk is preserved; a chunk
    that is ENTIRELY such entries collapses to '' and then matches nothing (intended —
    the index page is never the right citation target)."""
    if not text or "." not in text:
        return text
    return "\n".join(ln for ln in text.split("\n") if not _TOC_LEADER_RE.search(ln))


# ─── Header/footer de-weighting for citation grounding ──────────────────────
# A name or term in a running header/footer (page furniture, slide credits)
# repeats across pages and can outrank the body slide that actually covers the
# topic - e.g. "Mentorin Erika Mustermann, M.Sc." sits in the cover slide's FOOTER,
# so a citation grounds to the title page instead of the body page that lists the
# mentor with contact details. We split each page into body vs boilerplate and,
# when a keyword only matched the boilerplate, re-ground it onto the body page.
#
# Both boilerplate signals are LANGUAGE-AGNOSTIC by design (KIS is multi-tenant;
# other universities ingest PDFs in other languages):
#   1. docling region labels: ``data-label="Page-Header"`` / ``"Page-Footer"``.
#   2. line repetition: a line on >= ~half the pages is running furniture.
# No wordlists, no language assumptions.
# docling emits one labelled <div> per layout region. Page-Header/Footer =
# running furniture (boilerplate); every other label (Text, List-Group,
# Section-Header, Title, Table, …) is body content. We key off the LABEL, not
# the words, so it works for any language. The stored chunk ``content`` is an
# arbitrary character window of a "plain-text + layout-HTML" rendering — chunks
# may start mid-tag and aren't in reading order — so we only trust complete
# labelled divs we can extract, and ignore the duplicated plain-text rendering.
_LABELED_DIV_RE = re.compile(
    r'<div\b[^>]*\bdata-label="([^"]+)"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BOILER_LABELS = {"page-footer", "page-header"}


def _build_page_regions(raw_chunks: list) -> dict:
    """Split each PDF page into ``{"body": str, "boiler": str}`` (normalized).

    ``boiler`` = text in docling ``Page-Footer``/``Page-Header`` regions (running
    titles, page numbers, slide credits); ``body`` = every other labelled region.
    Lets the resolver de-weight a term that only matched page furniture. Pages
    whose chunks carry no usable labels get empty strings (→ no re-grounding,
    never worse). Language-agnostic: keys off region labels only, no wordlists.
    """
    by_page: dict = {}
    for c in raw_chunks:
        pn = c.get("page_number")
        if pn is None:
            continue
        by_page.setdefault(pn, []).append(c.get("content") or "")

    regions: dict = {}
    for pn, contents in by_page.items():
        full = "\n".join(contents)
        body_parts: list = []
        boiler_parts: list = []
        for label, inner in _LABELED_DIV_RE.findall(full):
            txt = _norm_for_match(_HTML_TAG_RE.sub(" ", inner))
            if not txt:
                continue
            if label.strip().lower() in _BOILER_LABELS:
                boiler_parts.append(txt)
            else:
                body_parts.append(txt)
        regions[pn] = {"body": " ".join(body_parts), "boiler": " ".join(boiler_parts)}
    return regions


def _best_body_anchor(nkw: str, regions: dict) -> "str | None":
    """Longest contiguous token sub-phrase of ``nkw`` (>= 2 tokens, >= 6 chars)
    that appears in some page's body text. Lets a boilerplate match re-ground
    onto the body page covering the term. Pure token windows - no wordlists."""
    toks = nkw.split()
    if len(toks) < 2:
        return None
    bodies = [r["body"] for r in regions.values()]
    for size in range(len(toks), 1, -1):
        for start in range(0, len(toks) - size + 1):
            phrase = " ".join(toks[start:start + size])
            if len(phrase) < 6:
                continue
            if any(phrase in b for b in bodies):
                return phrase
    return None


def _reroute_to_body(page: int, nkw: str, regions: dict) -> int:
    """De-weight a header/footer match: if ``nkw`` grounded to ``page`` only via
    its running header/footer (not body) and exactly one other page carries the
    term as body content, return that page. Otherwise keep ``page`` - so the
    result is never worse, and header/footer stays a valid fallback when no body
    page has the term."""
    if not regions:
        return page
    r = regions.get(page)
    if r is None or nkw in r["body"]:
        return page  # unknown page, or a genuine body match → keep
    anchor = _best_body_anchor(nkw, regions)
    if not anchor or anchor in r["body"]:
        return page
    # Only move with positive evidence the grounded match is boilerplate here
    # (anchor sits in THIS page's header/footer); avoids moving paraphrased body.
    if anchor not in r["boiler"]:
        return page
    body_hits = [pg for pg, rr in regions.items() if anchor in rr["body"]]
    if len(body_hits) == 1 and body_hits[0] != page:
        return body_hits[0]
    return page


def _resolve_citation_pages(text: str, source_index: dict) -> str:
    """Re-ground every citation's position against the real chunks.

    ``source_index`` maps source number N -> {
        "pages": set[int],            # REAL pages of this source (text/OCR chunks)
        "chunks": [ {"page": int|None, "start_time": float|None,
                     "norm_content": str}, ... ],   # the chunks shown to the model
    }

    Rules per citation ``[N, S.X | kw]`` / ``[N, MM:SS | kw]``:
      1. Unknown N -> drop.
      2. Keyword found verbatim in a chunk of N -> use THAT chunk's position
         (overrides whatever the model typed). For PDF the chunk page must be a
         REAL page; a media chunk's timestamp is always real.
      3. Keyword absent/unfindable, but the typed PDF page is REAL -> keep it
         (covers image pages and paraphrased keywords).
      4. Otherwise -> drop (unverifiable / hallucinated).

    ``pages`` is the source's real-page set, so a page invented by an upstream
    step (e.g. a ``[p.N]`` marker the model made up) is rejected too.
    """
    if not source_index:
        return text
    default_qnum = min(source_index)

    def _sub(m: "re.Match") -> str:
        qnum = int(m.group(1)) if m.group(1) else default_qnum
        page_str, time_str, kw_raw = m.group(2), m.group(3), m.group(4)
        kw = (kw_raw or "").strip().strip("\"'").strip()
        kw_suffix = f" | {kw}" if kw else ""
        entry = source_index.get(qnum)
        if entry is None:
            return ""  # rule 1: unknown source
        nkw = _norm_for_match(kw) if kw else ""
        # rule 2: ground via keyword in the real chunks the model was shown
        if nkw:
            for c in entry["chunks"]:
                if nkw not in c["norm_content"]:
                    continue
                if c.get("start_time") is not None:
                    return f"[{qnum}, {_format_timestamp(c['start_time'])}{kw_suffix}]"
                if c["page"] in entry["pages"]:
                    # De-weight header/footer: a term that only matched the page
                    # furniture (e.g. a name in the footer) re-grounds onto the
                    # body page that actually covers it.
                    pg = _reroute_to_body(c["page"], nkw, entry.get("page_regions"))
                    return f"[{qnum}, S. {pg}{kw_suffix}]"
                # matched chunk's page is not a real page (e.g. a hallucinated
                # page marker) -> keep looking, don't trust it
        # rule 3 (PDF): keep a real PDF page even without a keyword match (image
        # pages). A paraphrased keyword often fails rule 2 yet the model's typed
        # page is right - so still apply the header/footer de-weighting here: a
        # name the model cited from a footer credit re-grounds to its body page.
        if page_str is not None and int(page_str) in entry["pages"]:
            pg = _reroute_to_body(int(page_str), nkw, entry.get("page_regions")) if nkw else int(page_str)
            return f"[{qnum}, S. {pg}{kw_suffix}]"
        # rule 3 (media): keep a typed timestamp even without a keyword match. A
        # video/audio timestamp is always a valid seek target (unlike a page, it
        # cannot point to something that does not exist), so this is the media
        # analog of keeping a real PDF page above. Without it, paraphrased
        # keywords drop media citations wholesale - PDFs survive via the page
        # check, media had no equivalent and lost ~half their citations.
        if entry.get("is_media") and time_str is not None:
            return f"[{qnum}, {_format_timestamp(_parse_ts(time_str))}{kw_suffix}]"
        # rule 4: unverifiable -> drop
        return ""

    out = _CITE_RESOLVE_RE.sub(_sub, text)
    # Tidy whitespace left where citations were dropped (never touch newlines so
    # Markdown structure stays intact).
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


# The closing summary section restates the answer and must carry NO citations
# (the prompt asks the model to start it with a "## Zusammenfassung"/"## Summary"
# heading). We only match a heading whose WHOLE line is a summary keyword, so a
# mid-text bullet like "**Zusammenfassung von Quellen**: ..." is never caught.
_SUMMARY_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*[ \t]*)?"
    r"(?:Zusammenfassung|Zusammengefasst|Fazit|Summary|Conclusion)"
    r"[ \t]*(?:\*\*)?[ \t]*:?[ \t]*$"
)


def _strip_summary_citations(text: str) -> str:
    """Remove citation chips from the closing summary section.

    Finds the LAST standalone summary heading and strips every citation after it,
    leaving the body (with its citations) untouched. No heading -> no-op.
    """
    last = None
    for last in _SUMMARY_HEADING_RE.finditer(text):
        pass
    if last is None:
        return text
    head, tail = text[: last.end()], text[last.end():]
    # Only strip when a CITED body precedes the heading — that is what makes it a
    # genuine closing recap. If nothing cited comes before it, the heading is the
    # TITLE of a summary-style answer (the model loves to open "fasse zusammen"
    # output with a "Zusammenfassung" heading); stripping would then wipe every
    # chip in the whole answer.
    if not _CITE_RESOLVE_RE.search(head):
        return text
    tail = _CITE_RESOLVE_RE.sub("", tail)
    # Tidy whitespace left where citations were removed (keep newlines/markdown).
    tail = re.sub(r"[ \t]+([.,;:!?])", r"\1", tail)
    tail = re.sub(r"[ \t]{2,}", " ", tail)
    tail = re.sub(r"[ \t]+(\n|$)", r"\1", tail)  # drop trailing spaces at line/text end
    return head + tail


# Inline source references the model occasionally writes in prose despite the
# prompt forbidding it, e.g. "(siehe PDF 01 S. 6)" or "(VL1, 12:07)". They are
# NOT clickable chips. We convert them to bare `[N, pos]` chips (then let
# _resolve_citation_pages validate the position); if the source can't be mapped
# to a real document, we drop the parenthetical so no broken inline reference
# ever survives. We only touch parentheticals that carry a real position marker.
# Matches a parenthetical carrying a real position marker: "S. 6", "Seite 9",
# "Seiten 6-7" (the WORD form, but only when a number follows — so "(ca. 2 Seiten)"
# is NOT matched), or a "MM:SS" timestamp.
_INLINE_PAREN_RE = re.compile(
    r"\s*\(([^)]*?(?:S\.\s*\d+|Seiten?\s*\d+|\d{1,2}:\d{2})[^)]*?)\)", re.IGNORECASE
)
_INLINE_SRC_RE = re.compile(r"\b(PDF|Folie|Dokument|Doc|Quelle|Video|VL)\s*0*(\d{1,2})", re.IGNORECASE)
_INLINE_PAGE_RE = re.compile(r"(?:S\.|Seiten?)\s*(\d+)", re.IGNORECASE)


def _qnum_for_inline_token(num: int, want_media: bool, source_qmap: list) -> "int | None":
    """Map a token number (e.g. 1 from 'PDF 01' / 'VL1') to a document index N,
    matching a source whose filename carries that number (and the right media kind)."""
    for e in source_qmap:
        if bool(e.get("is_media")) != want_media:
            continue
        m = re.match(r"(?:vl)?0*(\d+)", str(e.get("filename", "")).lower())
        if m and int(m.group(1)) == num:
            return e.get("qnum")
    return None


def _chipify_inline_refs(text: str, source_qmap: list) -> str:
    """Turn prose inline source references into bare citation chips (or drop them)."""
    if not source_qmap:
        return text

    def _sub(m: "re.Match") -> str:
        body = m.group(1)
        src = _INLINE_SRC_RE.search(body)
        page = _INLINE_PAGE_RE.search(body)
        if page:
            # Page references are unambiguous; map the source or drop the ref.
            qnum = None
            if src and src.group(1).lower() not in ("video", "vl"):
                qnum = _qnum_for_inline_token(int(src.group(2)), False, source_qmap)
            return f" [{qnum}, S. {int(page.group(1))}]" if qnum else ""
        # Timestamp: only treat as a video position if a Video/VL token is present
        # (otherwise it is a clock time like 'Mittwoch 17:30' -> leave untouched).
        if src and src.group(1).lower() in ("video", "vl"):
            ts = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", body)
            if ts:
                qnum = _qnum_for_inline_token(int(src.group(2)), True, source_qmap)
                return f" [{qnum}, {ts.group(1)}]" if qnum else ""
        return m.group(0)  # not a mappable source ref -> leave as-is

    out = _INLINE_PAREN_RE.sub(_sub, text)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


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


class SourceUnitLoader:
    """Loads a source's position-bearing units once per request.

    PDF/doc/pptx -> page-chunks via get_aia_chunks_by_source. Media -> transcript
    segments via _load_transcript_segments.

    ``seen_pages_by_source`` (optional) maps source id -> the set of PDF pages the
    model actually saw in context. When given (and non-empty) for a source, PDF units
    are restricted to those pages, so a citation can only ever be grounded to a page
    the model could have used — not to some other page of the document that merely
    happens to contain the same words. Absent / empty set -> no restriction."""

    def __init__(self, seen_pages_by_source: "dict[int, set] | None" = None) -> None:
        self._cache: dict[int, list] = {}
        self._furniture: dict[int, set] = {}
        self._page_text_cache: dict = {}
        self._seen_pages = seen_pages_by_source or {}

    def offset_suffix(self, source: dict, page_number: int, claim: str) -> "str | None":
        """Architecture B: exact ``@start-end | span`` for a PDF citation, computed
        from the page's pdfium text (the same text the viewer loads). None when no
        confident span exists — caller then keeps its keyword/position-only chip."""
        from ._page_geometry import offset_suffix as _os
        return _os(source, page_number, claim, self._page_text_cache)

    def offset_suffixes(self, source: dict, page_number: int, claim: str) -> list[str]:
        """One ``@start-end | span`` per region the claim draws from on the page
        (primary first). Empty list when no confident span exists. The caller emits a
        chip per suffix; adjacent same-page chips merge into one multi-region highlight."""
        from ._page_geometry import offset_suffixes as _oss
        return _oss(source, page_number, claim, self._page_text_cache)

    def units(self, source: dict, *, is_media: bool) -> list:
        from ._citation_match import Unit
        sid = source["id"]
        if sid in self._cache:
            return self._cache[sid]
        if is_media:
            self._furniture[sid] = set()
            units = [
                Unit(page=None, start_time=s["start"], end_time=s["end"], raw_text=s["text"])
                for s in _load_transcript_segments(source)
            ]
        else:
            from src.features.ai_assistant.repository import chunks as chunk_repo
            raw = chunk_repo.get_aia_chunks_by_source(sid)
            furniture = _running_furniture(raw)
            self._furniture[sid] = furniture
            units = []
            for c in raw:
                if not c.get("content"):
                    continue
                body = _strip_furniture(c["content"], furniture)
                # Drop docling table/markup so matching + highlight anchors run on
                # clean visible text, never on HTML tag soup.
                body = _strip_html(body)
                body = body or _strip_html(c["content"])
                # Drop table-of-contents/index entries (dotted leader + page number) so a
                # claim never grounds to the index page instead of the real content section.
                body = _strip_toc_lines(body)
                units.append(Unit(page=c["page_number"], start_time=None,
                                  end_time=None, raw_text=body))
            # Restrict to the pages the model actually saw (when known), so a claim is
            # only ever grounded to a page it could have come from. Furniture is still
            # detected across ALL pages above; only the candidate set shrinks here.
            seen = self._seen_pages.get(sid)
            if seen:
                units = [u for u in units if u.page in seen]
        self._cache[sid] = units
        return units

    def furniture(self, source: dict) -> set:
        sid = source["id"]
        if sid not in self._furniture:
            self.units(source, is_media=False)  # populate (PDF path computes it)
        return self._furniture.get(sid, set())


def resolve_citation_positions(text: str, sources: dict, loader) -> str:
    """Re-anchor each [N, pos | kw] to the precise unit located by the matcher.

    sources: {qnum: {"source": row, "is_media": bool}} (same shape as coverage).
    Source-N prior: a model citation is only ever matched within source N's own
    units, never silently re-attributed to a different source."""
    from ._citation_match import match_query  # local: _citation_match imports from this module
    _get_furniture = getattr(loader, "furniture", None)
    _offset_suffixes = getattr(loader, "offset_suffixes", None)

    def _sub(m: "re.Match", line_text: str) -> str:
        qnum = int(m.group(1)) if m.group(1) else (min(sources) if sources else None)
        page_str, time_str, kw_raw = m.group(2), m.group(3), m.group(4)
        kw = (kw_raw or "").strip().strip("\"'").strip()
        # Strip docling HTML the model may have copied into the keyword (table chunks)
        # so neither the match nor the displayed keyword carries tag soup.
        kw = _strip_html(kw)
        meta = sources.get(qnum)
        if meta is None:
            return ""  # unknown source -> drop
        units = loader.units(meta["source"], is_media=meta["is_media"])
        furniture = _get_furniture(meta["source"]) if (_get_furniture and not meta["is_media"]) else set()
        # Drop a running header/footer keyword so the highlight can't land on furniture.
        # The model sometimes copies a footer line as the citation keyword because the
        # chunk text starts footer-first.
        if kw and furniture and _kw_is_furniture(kw, furniture):
            kw = ""   # running header/footer keyword -> re-ground below / position-only
        kw_suffix = f" | {kw}" if kw else ""
        typed = _parse_ts(time_str) if time_str else (int(page_str) if page_str else None)

        def _pdf_chip(page_n: int, fallback_suffix: str) -> str:
            """Build PDF chip(s), preferring exact ``@start-end | span`` offset anchors
            (Architecture B) computed from the cited line. A line that draws from several
            spots on the page yields one chip per region (adjacent, same source+page →
            merged client-side). Falls back to ``fallback_suffix`` when none is found."""
            if _offset_suffixes is not None and page_n is not None:
                try:
                    sufs = _offset_suffixes(meta["source"], page_n, line_text)
                except Exception:
                    sufs = None
                if sufs:
                    return " ".join(f"[{qnum}, S. {page_n}{s}]" for s in sufs)
            return f"[{qnum}, S. {page_n}{fallback_suffix}]"

        r = match_query(kw, units, typed_pos=typed, stem_match=meta["is_media"]) if kw else None
        if r and r.unit:
            if meta["is_media"]:
                return f"[{qnum}, {_format_timestamp(r.unit.start_time)}{kw_suffix}]"
            # Cross-check the keyword's page against the cited line's own text. The
            # model sometimes attaches a keyword that resolves to the WRONG page — a
            # section heading repeated across pages, or simply a mis-picked phrase
            # from a neighbouring page. When the line confidently and UNIQUELY matches
            # a different page (that is the bar _reground_by_line enforces), trust the
            # line — it is the actual claim — over the keyword's page.
            rg = _reground_by_line(line_text, units, furniture=furniture)
            if rg is not None and rg[0] != r.unit.page:
                page_n, anchor = rg
                return _pdf_chip(page_n, f" | {anchor}" if anchor else "")
            return _pdf_chip(r.unit.page, kw_suffix)
        # No keyword hit. Media: a timestamp is always a valid seek target, so keep
        # it as the model typed it (never fabricate one from the first segment).
        if meta["is_media"] and time_str is not None:
            return f"[{qnum}, {time_str}{kw_suffix}]"
        # PDF without a usable keyword: re-ground from the cited line's own text. The
        # model often gives a page-only chip (or a footer keyword we just dropped) and
        # frequently types the wrong page, so trust the line content over the typed page.
        if not meta["is_media"]:
            rg = _reground_by_line(line_text, units, furniture=furniture)
            if rg is not None:
                page_n, anchor = rg
                return _pdf_chip(page_n, f" | {anchor}" if anchor else "")
        # PDF: keep the typed page only if it is a REAL page of the source. Validate
        # against the source's page set (text/OCR chunks) so a page number the model
        # invented for a page that produced no chunk is dropped.
        if (not meta["is_media"]) and page_str is not None:
            valid_pages = meta.get("pages") or {u.page for u in units if u.page is not None}
            if int(page_str) in valid_pages:
                # The keyword did NOT match any unit and the line did not re-ground,
                # so it is unverified. Try an offset anchor from the line on this real
                # page anyway (the line may still locate even if the keyword was
                # bogus); otherwise fall back to a position-only chip that just
                # navigates to the page.
                return _pdf_chip(int(page_str), "")
        return ""  # unverifiable -> drop

    # Process line by line so the keyword-less re-grounding can use the cited line's
    # own text (with its citation tokens stripped) as the matching query.
    out_lines = []
    for line in text.split("\n"):
        line_text = _CITE_RESOLVE_RE.sub("", line)
        out_lines.append(_CITE_RESOLVE_RE.sub(lambda m, _lt=line_text: _sub(m, _lt), line))
    out = "\n".join(out_lines)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


def _dedup_line_chips(line: str) -> str:
    """Drop chips on a line that point to the SAME source + position as an earlier chip
    on that line (keep the first). The model — and the uncited-line filler — sometimes
    emit two chips for one claim that resolve to the identical spot, e.g.
    '... Fragen [1, 37:24 | a]. [1, 37:24 | b]'. The dedup key is the chip WITHOUT its
    keyword, so distinct highlight regions on the same page (different ``@start-end``
    offsets) are preserved while a truly identical position collapses. Per line only —
    the same position may legitimately recur on a different line/sentence."""
    seen: set = set()

    def _key(chip: str) -> str:
        # Everything up to the keyword separator: source + position (+ @offset), so two
        # chips differing only in their keyword (same visible '[N] pos') are duplicates.
        sep = max(chip.rfind("|"), chip.rfind("❘"))
        head = chip[:sep] if sep != -1 else chip.rstrip("]】")
        return re.sub(r"\s+", " ", head).strip().lower()

    def _sub(m: "re.Match") -> str:
        k = _key(m.group(0))
        if k in seen:
            return ""           # duplicate source+position -> drop this chip
        seen.add(k)
        return m.group(0)

    out = _CITE_RESOLVE_RE.sub(_sub, line)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.rstrip()


def _dedup_chips(text: str) -> str:
    """Apply :func:`_dedup_line_chips` per line (chip de-duplication is line-scoped)."""
    return "\n".join(_dedup_line_chips(line) for line in text.split("\n"))


import re as _re

_HEADING = _re.compile(r"^\s{0,3}#{1,6}\s")
_TABLE_SEP = _re.compile(r"^\s*\|?\s*:?-{2,}")
_LIST_OR_TEXT = _re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\S)")
# A Markdown thematic break / horizontal rule: 3+ of the same '-', '*' or '_'
# (optionally space-separated), nothing else. It is a separator, NOT a claim, so it
# must never receive a citation.
_THEMATIC_BREAK = _re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")


def is_citable_line(line: str, *, in_summary: bool) -> bool:
    """True if a filled citation may be appended to this line."""
    s = line.strip()
    if not s or in_summary:
        return False
    if _HEADING.match(line):
        return False
    if _THEMATIC_BREAK.match(s):
        return False
    if s.startswith("|") and _TABLE_SEP.match(s):
        return False
    if s.endswith(":"):           # intro/parent line, e.g. "... besteht aus:"
        return False
    if s.startswith("|"):          # table data row -> citable
        return True
    return bool(_LIST_OR_TEXT.match(line))


# A line "already has a citation" if it ends with a chip token.
# A line "already has a citation" if it ends with a chip token — optionally followed
# by a markdown table cell's closing pipe (the chip can sit inside the last cell).
_HAS_CITE = _re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*\|?\s*$")


def _kw_from_unit(unit, n_words: int = 4) -> str:
    """A short verbatim snippet from the matched unit for the highlight anchor.

    NOTE: the snippet is taken from the START of the unit, so for chunks that
    begin with page-number/header artefacts the highlight keyword may anchor at
    the wrong spot; acceptable for now, to be refined when the highlight is made
    precise.
    """
    return " ".join(unit.raw_text.split()[:n_words])


_DIGITS_ONLY = re.compile(r"^\W*\d{1,4}\W*$")  # a standalone page-number line


def _running_furniture(chunks: list) -> set:
    """Normalized text of running header/footer lines, detected language-agnostically
    by cross-page repetition: a line that appears on >= half the pages (min 2) is
    running furniture (page title, date, slide credit). No wordlists. Returns a set
    of normalized line strings."""
    from collections import Counter
    pages: dict = {}
    for c in chunks:
        pn = c.get("page_number")
        if pn is None:
            continue
        seen = pages.setdefault(pn, set())
        for raw in re.split(r"[\r\n]+", c.get("content") or ""):
            n = _norm_for_match(raw)
            if n:
                seen.add(n)  # dedupe within a page
    if len(pages) < 2:
        return set()
    counts: Counter = Counter()
    for lines in pages.values():
        for n in lines:
            counts[n] += 1
    threshold = max(2, (len(pages) + 1) // 2)
    return {n for n, c in counts.items() if c >= threshold}


def _kw_is_furniture(kw: str, furniture: set) -> bool:
    """True if the citation keyword is (part of) a running header/footer line, so it
    must not anchor a highlight. Matches either direction so a keyword that is a
    fragment of a furniture line, or that contains a whole furniture line, both count."""
    nkw = _norm_for_match(kw)
    if not nkw:
        return False
    for f in furniture:
        if len(f) >= 4 and (nkw in f or f in nkw):
            return True
    return False


def _strip_furniture(content: str, furniture: set) -> str:
    """Drop running-furniture lines and standalone page-number lines from a page's
    text, preserving the original case of the remaining body lines."""
    out = []
    for raw in re.split(r"[\r\n]+", content or ""):
        raw = raw.strip()
        if not raw:
            continue
        n = _norm_for_match(raw)
        if not n or n in furniture or _DIGITS_ONLY.match(raw):
            continue
        out.append(raw)
    return " ".join(out)


def _overlap_phrase(line: str, text: str, n_words: int = 5) -> str:
    """A short VERBATIM phrase from ``text`` that also occurs in the cited ``line``,
    so the highlight anchors on the actually-matched content (not the start of a
    coarse chunk). Falls back to the first words of ``text``."""
    body_words = _strip_html(text or "").split()
    if not body_words:
        return ""
    nline = _norm_for_match(line)
    for size in range(min(n_words, len(body_words)), 1, -1):
        for i in range(len(body_words) - size + 1):
            phrase = " ".join(body_words[i:i + size])
            if _norm_for_match(phrase) in nline:
                return phrase
    return " ".join(body_words[:n_words])


def _overlap_keyword(line: str, unit, n_words: int = 5) -> str:
    """``_overlap_phrase`` against a unit's body text."""
    return _overlap_phrase(line, unit.raw_text or "", n_words)


# Split a coarse page-chunk into sentence/bullet pieces so the highlight anchor can
# land on the matched sentence, not just somewhere on the right page. Splits on
# bullets and sentence punctuation; language-agnostic (no wordlists).
_SUBSEG_SPLIT = re.compile(r"(?:[•·•]|[.!?])\s+")


def _tokenset(s: str) -> set:
    """Word tokens of a raw string (normalize first). Mirrors _citation_match._tokens
    but kept local to avoid the circular import."""
    return set(re.findall(r"\w+", _norm_for_match(s), flags=re.UNICODE))


def _best_subsegment(line: str, unit_text: str) -> str:
    """Narrow a coarse page-chunk to the sentence/bullet whose tokens best overlap
    the cited line, so a keyword-less re-grounding anchors on the right sentence
    instead of the first bullet of the page."""
    qtok = _tokenset(line)
    if not qtok:
        return unit_text
    unit_text = _strip_html(unit_text)
    best, best_score = unit_text, -1.0
    for piece in _SUBSEG_SPLIT.split(unit_text):
        p = piece.strip()
        if not p:
            continue
        ptok = _tokenset(p)
        if not ptok:
            continue
        score = len(qtok & ptok) / len(qtok)
        if score > best_score:
            best, best_score = p, score
    return best


def _reground_by_line(line_text: str, units: list, *, furniture: set):
    """Re-locate a keyword-less PDF citation from the cited LINE's own text.

    Used when the model emitted a page-only chip (or its keyword was dropped as
    furniture) so there is no keyword to ground on. Returns (page, anchor) when the
    line confidently matches a unit, else None. ``anchor`` is a furniture-free
    verbatim phrase for the highlight (or "" if none survives)."""
    from ._citation_match import match_query  # local: avoids circular import
    q = (line_text or "").strip()
    if len(_tokenset(q)) < 2:        # too thin to ground safely
        return None
    r = match_query(q, units)
    if not r.unit or r.unit.page is None:
        return None
    # UNIQUENESS: only override the keyword's page when the line points at ONE page.
    # match_query's exact-substring branch has no uniqueness gate (and the fuzzy
    # branch's margin is bypassed here as we pass no typed_pos), so a line whose text
    # appears verbatim on several pages would otherwise resolve to the earliest unit.
    # When that happens the line is ambiguous -> keep the keyword's page.
    if r.match_type == "exact":
        nq = _norm_for_match(q)
        if len({u.page for u in units if nq in u.normalized() and u.page is not None}) > 1:
            return None
    sub = _best_subsegment(q, r.unit.raw_text or "")
    anchor = _overlap_phrase(q, sub)
    if anchor and _kw_is_furniture(anchor, furniture):
        anchor = ""
    return (r.unit.page, anchor)


_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def _main_clause(line: str) -> str:
    """A bullet's core claim with any parenthetical gloss removed. Hilde often adds
    an explanatory aside in parentheses that is NOT in the source ("… (Kein Abdriften
    während der Recherche.)"); those extra words drag token-containment below the
    match threshold even though the main clause grounds cleanly."""
    return _PARENTHETICAL.sub(" ", line).strip()


def fill_uncited_lines(text: str, sources: dict, loader) -> str:
    """Append a citation to each groundable line that lacks one.

    sources: {qnum: {"source": <row dict>, "is_media": bool}}
    loader:  SourceUnitLoader (or any object with .units(source, is_media=...))."""
    # Local import: _citation_match imports from _helpers, so a module-level
    # import would create a circular dependency.
    from ._citation_match import match_query_multi  # noqa: PLC0415
    _offset_suffixes = getattr(loader, "offset_suffixes", None)

    def _best_match(query: str):
        # Best source by its top score; carry that source's near-tie units so an
        # ambiguous claim (equal on several pages) yields a chip per page, not none.
        best = None  # (top_score, qnum, [units], is_media)
        for qnum, meta in sources.items():
            units = loader.units(meta["source"], is_media=meta["is_media"])
            # Media: stem-aware matching so a paraphrased spoken-language line still
            # grounds ("Schneeballprinzip" ↔ "Schneeballsystem"). PDF stays exact.
            rs = match_query_multi(query, units, stem_match=meta["is_media"])
            if rs and (best is None or rs[0].score > best[0]):
                best = (rs[0].score, qnum, [r.unit for r in rs], meta["is_media"])
        return best

    out_lines, in_summary = [], False
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if _SUMMARY_HEADING_RE.match(line):
            in_summary = True
        # A table header row (the one directly above the |---|---| delimiter) is a
        # column title, not a claim -> never cite it.
        is_table_header = (line.lstrip().startswith("|")
                           and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()))
        if (not is_citable_line(line, in_summary=in_summary)
                or is_table_header or _HAS_CITE.search(line.rstrip())):
            out_lines.append(line)
            continue
        match_text = line
        best = _best_match(line)
        if best is None:
            # Retry on the main clause: a parenthetical gloss that is not in the
            # source can push the full line below threshold.
            mc = _main_clause(line)
            if mc != line and len(_tokenset(mc)) >= 2:
                best = _best_match(mc)
                match_text = mc
        if best is None:
            out_lines.append(line)          # below threshold -> deliberately no chip
            continue
        _, qnum, units_hit, is_media = best
        source = sources[qnum]["source"]

        def _anchor(unit):
            # Narrow a coarse page-chunk to the matched sentence first, so the anchor
            # lands on the right sentence (not the first overlapping word on the page).
            kw = _overlap_phrase(match_text, _best_subsegment(match_text, unit.raw_text or ""))
            pos = _format_timestamp(unit.start_time) if is_media else f"S. {unit.page}"
            # Architecture B: exact ``@start-end | span`` offset anchor(s) for PDF citations.
            offs: list[str] = []
            if not is_media and _offset_suffixes is not None and unit.page is not None:
                try:
                    offs = _offset_suffixes(source, unit.page, match_text) or []
                except Exception:
                    offs = []
            return pos, kw, offs

        stripped = line.rstrip()
        is_table = stripped.startswith("|") and stripped.endswith("|")
        if len(units_hit) == 1:
            pos, kw, offs = _anchor(units_hit[0])
            if is_table:
                # Markdown table row: put the chip INSIDE the last cell (before the closing
                # pipe) so it renders, and use the non-pipe separator ❘ so the span/keyword
                # text can never split the cell.
                off0 = offs[0] if offs else None
                body = off0.replace(" | ", " ❘ ", 1) if off0 else f" ❘ {kw}"
                out_lines.append(f"{stripped[:-1].rstrip()} [{qnum}, {pos}{body}] |")
            elif offs:
                # One chip per region; adjacent same-source+page chips merge client-side.
                out_lines.append(stripped + "".join(f" [{qnum}, {pos}{s}]" for s in offs))
            else:
                out_lines.append(f"{stripped} [{qnum}, {pos} | {kw}]")
        else:
            # Ambiguous: the claim grounds equally on several pages the model saw -> one
            # chip per page (its primary offset region or keyword). Better to show every
            # candidate source than to drop the chip or gamble on the wrong page.
            chips = []
            for unit in units_hit:
                pos, kw, offs = _anchor(unit)
                body = offs[0] if offs else f" | {kw}"
                chips.append(f"[{qnum}, {pos}{body}]")
            if is_table:
                cell = " ".join(c.replace(" | ", " ❘ ", 1) for c in chips)
                out_lines.append(f"{stripped[:-1].rstrip()} {cell} |")
            else:
                out_lines.append(stripped + " " + " ".join(chips))
    return "\n".join(out_lines)

