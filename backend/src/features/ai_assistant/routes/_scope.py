"""Serves an explicit page or time reference straight from those spots."""

import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from src import database as db

from ._media_files import _MEDIA_EXTENSIONS


# A page reference in the question is fetched directly instead of searched.
_PAGE_REF_RE = re.compile(
    r"\b(?:S\.\s*|Seiten?\s*|pp?\.\s*|pages?\s*)"
    r"(\d{1,4})"
    # Range separators, a bare space does not count as a range.
    r"(?:\s*(?:[-–—]+\s*(?:bis|to)?|bis|to)\s*[-–—]*\s*(\d{1,4}))?",
    re.IGNORECASE,
)


_MAX_PAGE_SPAN = 50


def _parse_page_refs(question: str) -> list[int]:
    """Pulls explicit page numbers out of a question, sorted and without duplicates."""
    pages: set[int] = set()
    for m in _PAGE_REF_RE.finditer(question or ""):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if end < start:
            start, end = end, start
        if end - start > _MAX_PAGE_SPAN:
            end = start
        pages.update(range(start, end + 1))
    return sorted(pages)


def _first_source_kind(source_ids: Optional[list[int]], sources_by_id: dict[int, dict]) -> Optional[str]:
    """Classifies the first chosen source as PDF, media or None."""
    if not source_ids:
        return None
    src = sources_by_id.get(source_ids[0])
    if not src:
        return None
    suffix = Path(src["filename"]).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in _MEDIA_EXTENSIONS:
        return "media"
    return None


def _parse_scope_response(content: str) -> dict:
    """Reads the reference call's answer leniently, nonsense yields an empty reference."""
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"unit": None, "intervals": []}
    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"unit": None, "intervals": []}
    unit = data.get("unit")
    if unit not in ("page", "time", "unknown"):
        unit = None
    intervals: list[list] = []
    for it in data.get("intervals") or []:
        if not isinstance(it, (list, tuple)) or len(it) != 2:
            continue
        a, b = it
        if not isinstance(a, int) or isinstance(a, bool):
            continue
        if b is not None and (not isinstance(b, int) or isinstance(b, bool)):
            continue
        intervals.append([a, b])
    return {"unit": unit, "intervals": intervals}


_MAX_TIME_SPAN_SEC = 6 * 3600  # safety cap so an open/absurd time range can't pull everything


def _expand_page_intervals(intervals: list[list], max_page: Optional[int]) -> list[int]:
    """Expands page ranges into a sorted page list."""
    pages: set[int] = set()
    for a, b in intervals:
        if b is None:
            b = max_page if max_page is not None else a
        lo, hi = (a, b) if a <= b else (b, a)
        if hi - lo > _MAX_PAGE_SPAN:
            hi = lo
        pages.update(range(lo, hi + 1))
    return sorted(p for p in pages if p >= 1)


def _servable_scope_intervals(unit: Optional[str], intervals: list[list]) -> list[list]:
    """Drops ranges that are almost certainly no real page or time reference."""
    if unit != "unknown":
        return intervals
    return [iv for iv in intervals if iv[1] is not None]


def _page_scope_too_large(intervals: list[list], max_page: Optional[int], limit: int) -> bool:
    """True when the page reference covers nearly the whole document and is thus an overview."""
    total = 0
    for a, b in intervals:
        if b is None:
            b = max_page if max_page is not None else a
        lo, hi = (a, b) if a <= b else (b, a)
        total += hi - lo + 1
        if total > limit:
            return True
    return False


def _time_intervals_to_seconds(intervals: list[list], max_seconds: Optional[float]) -> list[tuple]:
    """Turns minute ranges into second windows, capped against absurd spans."""
    out: list[tuple] = []
    for a, b in intervals:
        if b is None:
            lo = max(0, a)
            lo_sec = lo * 60
            hi_sec = max_seconds if max_seconds is not None else (lo + 1) * 60
        else:
            lo, hi = (a, b) if a <= b else (b, a)
            lo_sec, hi_sec = max(0, lo) * 60, (hi + 1) * 60
        if hi_sec - lo_sec > _MAX_TIME_SPAN_SEC:
            hi_sec = lo_sec + 60
        out.append((lo_sec, hi_sec))
    return out


def _retrieve_page_scoped_context(source_ids: list[int], pages: list[int]) -> list[dict]:
    """Loads the chunks of the sources and keeps only the requested pages."""
    wanted = set(pages)
    chunks: list[dict] = []
    for sid in source_ids:
        chunks.extend(
            c for c in db.get_aia_chunks_by_source(sid) if c.get("page_number") in wanted
        )
    return chunks


def _retrieve_time_scoped_context(source_id: int, ranges_seconds: list[tuple]) -> list[dict]:
    """Loads a medium's chunks and keeps those that fall into the time window."""
    chunks: list[dict] = []
    for c in db.get_aia_chunks_by_source(source_id):
        st = c.get("start_time")
        if st is None:
            continue
        en = c.get("end_time")
        if en is None:
            en = st
        if any(st < r_end and en > r_start for r_start, r_end in ranges_seconds):
            chunks.append(c)
    return chunks


# Refusal for a reference that cannot be served, worded differently from the content one.
_SCOPE_UNFULFILLABLE_MSG = {
    "de": "Dabei kann ich dir leider nicht weiterhelfen. Bitte formuliere deine Frage anders oder wähle das passende Material aus.",
    "en": "I'm afraid I can't help with that. Please rephrase your question or select the relevant source.",
}


def _scope_unfulfillable_message(scope_requested: bool, scope_chunks, chat_lang: str) -> Optional[str]:
    """Message for when a requested page or time reference could not be served."""
    if scope_requested and not scope_chunks:
        return _SCOPE_UNFULFILLABLE_MSG.get(chat_lang, _SCOPE_UNFULFILLABLE_MSG["de"])
    return None


def resolve_scope(scope_raw, *, question: str, source_text, umformen: bool,
                  source_ids, resolved_sources: dict, intent: str) -> tuple:
    """Serves a page or time reference from those spots, or hands the question back."""
    # A page or time reference is served from exactly these spots, not searched.
    scope_chunks: Optional[list[dict]] = None
    scope_requested = False
    if not source_text and not umformen:
        unit = scope_raw["unit"] if scope_raw else None
        intervals = scope_raw["intervals"] if scope_raw else []
        # An open range of bare numbers is a date, not a page reference.
        intervals = _servable_scope_intervals(unit, intervals)
        # Pattern-based last resort when the pre-call returned no reference.
        if not intervals:
            rx = _parse_page_refs(question)
            if rx:
                unit, intervals = "page", [[p, p] for p in rx]
        if intervals:
            kind = _first_source_kind(source_ids, resolved_sources)  # "pdf"|"media"|None
            # An explicit reference may refuse, bare numbers fall back into the search.
            explicit = unit in ("page", "time")
            scope_requested = explicit
            eff_unit = unit if explicit else (
                "page" if kind == "pdf" else "time" if kind == "media" else None)
            first_id = source_ids[0] if source_ids else None
            if first_id and eff_unit == "page" and kind == "pdf":
                max_page = max(db.get_source_page_numbers(first_id), default=None)
                if _page_scope_too_large(intervals, max_page, _MAX_PAGE_SPAN):
                    # A range over half the document is an overview, not a reference.
                    intent = "GENERIC"
                    scope_requested = False
                    logger.info("Page scope too large (> {} pages) → routing to GENERIC overview", _MAX_PAGE_SPAN)
                else:
                    pages = _expand_page_intervals(intervals, max_page)
                    scope_chunks = _retrieve_page_scoped_context([first_id], pages)
                    logger.info("Page-scoped retrieval: pages {} → {} chunks (source={})",
                                pages, len(scope_chunks or []), first_id)
            elif first_id and eff_unit == "time" and kind == "media":
                media = db.get_aia_chunks_by_source(first_id)
                max_sec = max((c.get("end_time") or c.get("start_time") or 0 for c in media), default=None)
                ranges = _time_intervals_to_seconds(intervals, max_sec)
                scope_chunks = _retrieve_time_scoped_context(first_id, ranges)
                logger.info("Time-scoped retrieval: {} → {} chunks (source={})",
                            ranges, len(scope_chunks or []), first_id)
            else:
                logger.info("Scope requested (unit={}, kind={}) — not servable", unit, kind)
    return intent, scope_chunks, scope_requested
