"""Source-text scanner: builds date/TBD candidates from a source's chunks."""

from src import database as db

from src.features.ai_assistant.tasks.studio.schedule._regex import (
    _TBD_PATTERNS,
    _date_candidates_in_text,
)
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _normalize_date,
    _normalize_partial_date,
)


def _load_source_chunks(source_id: int) -> list[dict]:
    """Return ordered chunks with their positions (page or timestamp)."""
    chunks = db.get_aia_chunks_by_source(source_id)
    if not chunks:
        return []
    return sorted(
        chunks,
        key=lambda c: (c.get("start_time") or 0, c.get("page_number") or 0, c.get("id", 0)),
    )


def _build_candidates_for_source(src: dict) -> list[dict]:
    """Find all date candidates in a source. Year-full matches produce date_iso;
    year-less matches produce partial_date=(month, day), resolved to current year.
    'To-be-arranged'-style phrases produce is_tbd=True with no date.
    """
    candidates: list[dict] = []
    for c in _load_source_chunks(src["id"]):
        content = c.get("content") or ""
        if not content:
            continue
        page = c.get("page_number")
        st = c.get("start_time")

        # Date-based candidates
        for s, e, raw_date, has_year in _date_candidates_in_text(content):
            if has_year:
                norm = _normalize_date(raw_date)
                if not norm:
                    continue
                partial = None
                date_iso = norm
            else:
                partial = _normalize_partial_date(raw_date)
                if partial is None:
                    continue
                date_iso = None
            # +/-450 chars so table headers with time (e.g. "17:30") at the top of a
            # schedule listing are visible to the classifier for every row below.
            ctx_start = max(0, s - 450)
            ctx_end = min(len(content), e + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            # Short snippet for the frontend highlight search. Start AT the date
            # (no chars before) so the PDF-viewer match lands on the date and
            # doesn't bleed into the preceding bullet. Stop at the next newline
            # to catch exactly one bullet/line; cap at 200 chars for safety.
            nl_pos = content.find("\n", e)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": raw_date,
                "date_iso": date_iso,
                "partial_date": partial,
                "is_tbd": False,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st,
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })

        # TBD candidates ("nach Vereinbarung" etc.): no date, but a real event
        # whose scheduling is still open. Dedup per chunk: one TBD candidate even
        # if the phrase appears multiple times on the same page.
        tbd_seen = False
        for pat in _TBD_PATTERNS:
            if tbd_seen:
                break
            for m in pat.finditer(content):
                ctx_start = max(0, m.start() - 300)
                ctx_end = min(len(content), m.end() + 300)
                ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
                # Start AT the TBD phrase; stop at next newline (bullet end).
                nl_pos = content.find("\n", m.end())
                hl_end = min(len(content), m.start() + 200)
                if nl_pos != -1 and nl_pos < hl_end:
                    hl_end = nl_pos
                quote = content[m.start():hl_end].replace("\n", " ").strip()
                candidates.append({
                    "date_raw": m.group("phrase"),
                    "date_iso": None,
                    "partial_date": None,
                    "is_tbd": True,
                    "context": ctx,
                    "raw_quote": quote,
                    "page_number": page,
                    "start_time": st,
                    "source_uuid": src["uuid"],
                    "source_filename": src.get("filename") or "",
                })
                tbd_seen = True
                break
    return candidates
