"""KI-Assistent Celery tasks — zeitplan extraction (Regex + Batch-Classify pipeline)."""

import json
import re
import time as _time
from datetime import date, time
from difflib import SequenceMatcher
from typing import Optional

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.tool_prompts import (
    KIA_ZEITPLAN_CLASSIFY_PROMPT,
    KIA_ZEITPLAN_HARMONIZE_PROMPT,
)
from src.features.ki_assistent.tasks._helpers import _get_llm_client, _clean_llm_json

# Classify/harmonize batches can carry up to 30 candidates with ±450 chars of
# context each → responses up to 10k tokens. 120s (OpenAI default) is too tight
# for slower providers; 180s + one retry covers transient stalls.
_CLASSIFY_TIMEOUT_SECS = 180
_CLASSIFY_RETRY_WAIT_SECS = 5


# ─── Helpers ────────────────────────────────────────────────────────────────

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parse_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, TypeError, IndexError):
        return None


def _fmt_hms(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _norm_title(t: str) -> str:
    """Lower-case + whitespace/separator collapse. Language-agnostic."""
    raw = str(t or "").lower()
    for sep in "/:-_()[]{}|\"'":
        raw = raw.replace(sep, " ")
    return " ".join(raw.split())


def _token_overlap(a: str, b: str) -> float:
    """Fraction of shorter token set that also appears in the longer one.
    Handles stem-like matches by simple prefix comparison for 5+ char tokens.
    Digit-only tokens (years, day numbers, month numbers) are excluded — they
    carry no semantic signal about the event itself.
    Language-agnostic.
    """
    ta = set(t for t in _norm_title(a).split() if len(t) >= 3 and not t.isdigit())
    tb = set(t for t in _norm_title(b).split() if len(t) >= 3 and not t.isdigit())
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    hits = 0
    for t in small:
        if t in large:
            hits += 1
            continue
        # prefix match for stem variants: 'sprechstunde' matches 'sprechstunden'
        if len(t) >= 5 and any(
            (t.startswith(x[:5]) or x.startswith(t[:5])) for x in large
        ):
            hits += 1
    return hits / len(small)


def _fuzzy_same(a: str, b: str) -> bool:
    """Merge candidate and existing entry if titles are similar by EITHER
    character-level similarity (difflib >= 0.75) OR content-token overlap (>= 0.7).
    Both are language-agnostic.
    """
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if SequenceMatcher(None, na, nb).ratio() >= 0.75:
        return True
    if _token_overlap(a, b) >= 0.7:
        return True
    return False


# ─── Source text loader (positions preserved) ──────────────────────────────

def _load_source_chunks(source_id: int) -> list[dict]:
    """Return ordered chunks with their positions (page or timestamp)."""
    chunks = db.get_kia_chunks_by_source(source_id)
    if not chunks:
        return []
    return sorted(
        chunks,
        key=lambda c: (c.get("start_time") or 0, c.get("page_number") or 0, c.get("id", 0)),
    )


# ─── Regex-based date extraction ───────────────────────────────────────────

# German + ISO + mixed patterns. Captures anchored date strings so the LLM
# only has to classify, not find.
_MONTH_DE = (
    "januar|februar|märz|maerz|april|mai|juni|juli|august|"
    "september|oktober|november|dezember|jan|feb|mär|mar|apr|"
    "jun|jul|aug|sep|sept|okt|nov|dez"
)
_MONTH_EN = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december|jan|feb|mar|apr|"
    "jun|jul|aug|sep|sept|oct|nov|dec"
)

_DATE_PATTERNS_WITH_YEAR = [
    # DD.MM.YYYY
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\b"),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b"),
    # D. Month YYYY (German) — e.g. "15. Juli 2026"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\s+\d{{4}})\b", re.IGNORECASE),
    # Month D, YYYY (English) — e.g. "July 15, 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
]

_DATE_PATTERNS_YEARLESS = [
    # DD.MM. (German short, no year) — e.g. "03.07." or "3.7."
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.)(?!\d)"),
    # D. Month (German, no year) — e.g. "15. Juli"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE}))(?!\s+\d{{4}})\b", re.IGNORECASE),
    # Month D (English, no year) — e.g. "July 15"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}})(?!,?\s*\d{{4}})\b", re.IGNORECASE),
]

# "Date not yet fixed" patterns: the event is real but happens at a time still
# to be negotiated. We surface these so the schedule shows them as a separate
# 'Nach Vereinbarung' block in the UI.
_TBD_PATTERNS = [
    re.compile(
        r"(?P<phrase>nach\s+(?:individueller\s+)?(?:Vereinbarung|Absprache)"
        r"|Terminabsprache"
        r"|Termin\s+(?:wird|werden)\s+vereinbart"
        r"|zeitlich\s+nach\s+Absprache"
        r"|Datum\s+nach\s+Absprache"
        r"|to\s+be\s+(?:announced|decided|confirmed)"
        r"|TBA|TBD|TBC)",
        re.IGNORECASE,
    ),
]


def _date_candidates_in_text(text: str) -> list[tuple[int, int, str, bool]]:
    """Return list of (start_index, end_index, matched_string, has_year).
    Year-full matches win over year-less at overlapping positions.
    """
    found: list[tuple[int, int, str, bool]] = []
    for pat in _DATE_PATTERNS_WITH_YEAR:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True))
    for pat in _DATE_PATTERNS_YEARLESS:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), False))
    # Deduplicate: prefer has_year=True, then longer span, then earliest start
    found.sort(key=lambda t: (t[0], not t[3], -(t[1] - t[0])))
    result: list[tuple[int, int, str, bool]] = []
    last_end = -1
    for s, e, d, hy in found:
        if s >= last_end:
            result.append((s, e, d, hy))
            last_end = e
    return result


_MONTHS = {
    "januar": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dez": 12, "dec": 12,
}


def _normalize_date(raw: str) -> Optional[str]:
    """Convert a matched year-FULL date string to ISO 'YYYY-MM-DD'. Returns None on failure."""
    s = raw.strip().replace("\u00a0", " ")
    # ISO
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD.MM.YYYY
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # D. Month YYYY (German)
    m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜüß]+)\s+(\d{4})", s)
    if m:
        d, mo_str, y = m.groups()
        mo = _MONTHS.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    # Month D, YYYY (English)
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m:
        mo_str, d, y = m.groups()
        mo = _MONTHS.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    return None


def _normalize_partial_date(raw: str) -> Optional[tuple[int, int]]:
    """Year-less date → (month, day). Returns None on failure."""
    s = raw.strip().replace("\u00a0", " ")
    # DD.MM.
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.", s)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        return (mo, d) if 1 <= mo <= 12 and 1 <= d <= 31 else None
    # D. Month (German)
    m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜüß]+)", s)
    if m:
        d = int(m.group(1))
        mo = _MONTHS.get(m.group(2).lower())
        if mo and 1 <= d <= 31:
            return (mo, d)
    # Month D (English)
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})", s)
    if m:
        mo = _MONTHS.get(m.group(1).lower())
        d = int(m.group(2))
        if mo and 1 <= d <= 31:
            return (mo, d)
    return None


def _resolve_current_year(today_d: date, month: int, day: int) -> Optional[date]:
    """Year-less dates ALWAYS resolve to the current year. If the resulting date
    is in the past, it's shown dimmed by the UI — we do NOT hallucinate a future
    year. Returns None on invalid MD."""
    try:
        return date(today_d.year, month, day)
    except ValueError:
        return None


def _build_candidates_for_source(src: dict) -> list[dict]:
    """Find all date candidates in a source. Year-full matches produce date_iso;
    year-less matches produce partial_date=(month, day), resolved to current year.
    'Nach Vereinbarung'-style phrases produce is_tbd=True with no date.
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
            # ±450 chars so table headers with time (e.g. "17:30") at the top of a
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

        # TBD candidates ("nach Vereinbarung" etc.) — no date, but a real event
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


# ─── Batch classification via single LLM call ──────────────────────────────

_CLASSIFY_BATCH_SIZE = 30  # safe size so a ~10k-token response stays within limits


def _classify_candidates_batch(client, model, batch: list[dict], today_d: date) -> list[dict]:
    """One LLM call for up to ~30 candidates. Returns classifications aligned to batch order."""
    payload = []
    for i, c in enumerate(batch):
        item = {
            "id": i,
            "date_raw": c["date_raw"],
            "date_iso": c["date_iso"],
            "context": c["context"],
        }
        if c.get("partial_date"):
            mo, da = c["partial_date"]
            item["partial_month_day"] = f"{mo:02d}-{da:02d}"
            item["year_missing"] = True
        if c.get("is_tbd"):
            item["date_tbd"] = True
        payload.append(item)

    user_msg = (
        f"Current date (today): {today_d.isoformat()}.\n\n"
        "Classify each candidate below. If a candidate has year_missing=true, "
        "the system will resolve it to the NEXT upcoming occurrence after today. "
        "Drop it (keep=false) if the context shows it is historical or merely referential.\n\n"
        'Return a JSON object with key "results" as an array of the same length (same ids).\n\n'
        "Candidates:\n" + json.dumps(payload, ensure_ascii=False)
    )
    response = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": KIA_ZEITPLAN_CLASSIFY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=10000,
                response_format={"type": "json_object"},
                timeout=_CLASSIFY_TIMEOUT_SECS,
            )
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                raise
            if "timeout" in err_str.lower() and attempt == 0:
                logger.warning("Zeitplan classify: timeout, retrying once in {}s", _CLASSIFY_RETRY_WAIT_SECS)
                _time.sleep(_CLASSIFY_RETRY_WAIT_SECS)
                continue
            raise
    raw = (response.choices[0].message.content or "").strip()
    raw = _clean_llm_json(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Zeitplan-Classify JSON decode failed. Raw tail:\n{}", raw[-2000:])
        raise e

    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        raise ValueError("Classifier did not return a 'results' array")

    by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
    out: list[dict] = []
    for i in range(len(batch)):
        r = by_id.get(i) or {}
        keep = bool(r.get("keep"))
        is_footer = bool(r.get("is_footer"))
        is_historical = bool(r.get("is_historical"))
        # Hard-drop footers and historical references
        if is_footer or is_historical:
            keep = False
        out.append({
            "keep": keep,
            "is_footer": is_footer,
            "is_historical": is_historical,
            "type": r.get("type") or "termin",
            "title": (r.get("title") or "").strip(),
            "description": (r.get("description") or None),
            "due_time": (r.get("due_time") or None),
            "is_optional": bool(r.get("is_optional")),
        })
    return out


def _harmonize_same_date_titles(
    client, model, all_candidates: list[dict], classifications: list[dict],
    today_d: date, existing_entries: list[dict],
) -> None:
    """Cross-candidate dedup pass. Shows the LLM ALL events on one date —
    both new candidates (title can be rewritten) and existing DB entries
    (title is fixed). The LLM groups same-events; any new candidate whose
    group contains an existing entry gets rewritten to that existing title,
    so fuzzy-merge downstream picks it up instead of creating a duplicate.
    Mutates `classifications` in place.
    """
    from collections import defaultdict
    cand_groups: dict[date, list[int]] = defaultdict(list)
    for idx, (cand, cls) in enumerate(zip(all_candidates, classifications)):
        if not cls["keep"] or cls["is_footer"] or cls.get("is_historical"):
            continue
        if cand.get("date_iso"):
            d = _parse_date(cand["date_iso"])
        elif cand.get("partial_date"):
            mo, da = cand["partial_date"]
            d = _resolve_current_year(today_d, mo, da)
        else:
            d = None
        if d is not None:
            cand_groups[d].append(idx)

    existing_by_date: dict[date, list[dict]] = defaultdict(list)
    for e in existing_entries:
        d = e.get("due_date")
        if d is not None:
            existing_by_date[d].append(e)

    for d, indices in cand_groups.items():
        existing_at_d = existing_by_date.get(d, [])
        titles = {classifications[i]["title"] for i in indices}
        # Skip only if: no existing entries AND candidates already share a title
        if not existing_at_d and len(titles) <= 1:
            continue

        items: list[dict] = []
        for i in indices:
            items.append({
                "id": f"c{i}",  # 'c' prefix = candidate (rewritable)
                "role": "candidate",
                "title": classifications[i]["title"],
                "description": classifications[i].get("description"),
                "type": classifications[i]["type"],
            })
        for e in existing_at_d:
            items.append({
                "id": f"e{e['id']}",  # 'e' prefix = existing (fixed title)
                "role": "existing",
                "title": e.get("title") or "",
                "description": e.get("description"),
                "type": e.get("type"),
            })

        user_msg = (
            f"Date: {d.isoformat()}\n"
            "Some items are NEW candidates (role=candidate, title can be rewritten).\n"
            "Others are EXISTING entries in the DB (role=existing, title is fixed).\n"
            "If a candidate describes the SAME event as an existing entry, put them\n"
            "in the same group AND set canonical_title = the existing entry's title.\n\n"
            f"Events on this date:\n{json.dumps(items, ensure_ascii=False)}"
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": KIA_ZEITPLAN_HARMONIZE_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=_CLASSIFY_TIMEOUT_SECS,
            )
            raw = _clean_llm_json((response.choices[0].message.content or "").strip())
            parsed = json.loads(raw)
            groups_out = parsed.get("groups") or []
            for g in groups_out:
                ids = g.get("ids") or []
                canonical = (g.get("canonical_title") or "").strip()
                if not canonical:
                    continue
                # Only rewrite candidates (c-prefixed); existing entries stay fixed.
                cand_ids = [int(i[1:]) for i in ids if isinstance(i, str) and i.startswith("c") and i[1:].isdigit()]
                if not cand_ids:
                    continue
                for i in cand_ids:
                    if 0 <= i < len(classifications):
                        classifications[i]["title"] = canonical
                logger.info(
                    "Zeitplan harmonize: date {} — candidates {} aligned to '{}'",
                    d.isoformat(), cand_ids, canonical,
                )
        except Exception as e:
            logger.warning("Zeitplan harmonize failed for {}: {}", d.isoformat(), e)


def _classify_candidates(client, model, candidates: list[dict], today_d: date) -> list[dict]:
    """Split candidates into batches of _CLASSIFY_BATCH_SIZE and classify each.
    Returns a flat list aligned with `candidates`.
    """
    if not candidates:
        return []
    all_results: list[dict] = []
    n = len(candidates)
    for start in range(0, n, _CLASSIFY_BATCH_SIZE):
        batch = candidates[start:start + _CLASSIFY_BATCH_SIZE]
        logger.info("Zeitplan classify batch {}/{} ({} candidates)",
                    start // _CLASSIFY_BATCH_SIZE + 1,
                    (n + _CLASSIFY_BATCH_SIZE - 1) // _CLASSIFY_BATCH_SIZE,
                    len(batch))
        all_results.extend(_classify_candidates_batch(client, model, batch, today_d))
    return all_results


# ─── Celery task ───────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="kia.generate_zeitplan", queue="kia",
                 soft_time_limit=600, time_limit=720)
@observe(name="kia-zeitplan")
def run_generate_zeitplan(self, job_id: int, module_id: int, user_id: int,
                          source_uuids: list[str]):
    """Regex-first pipeline:
      1) find all date candidates per source via regex (100% recall)
      2) classify all candidates in ONE LLM call (is_event? footer? type? title?)
      3) merge into existing entries (fuzzy-title + same date → append source_ref)
    """
    try:
        db.update_zeitplan_job(job_id, "running")
        logger.info("Zeitplan job {} started", job_id)

        sources: list[dict] = []
        for suuid in source_uuids:
            src = db.get_kia_source(suuid)
            if src and src["module_id"] == module_id:
                sources.append(src)

        already_processed = set(db.get_processed_source_ids(module_id, user_id))
        pending = [s for s in sources if s["id"] not in already_processed]

        if not pending:
            db.update_zeitplan_job(job_id, "success", added_count=0)
            logger.info("Zeitplan job {}: no pending sources", job_id)
            return

        # STAGE 1: Regex-based candidate collection (across all pending sources)
        all_candidates: list[dict] = []
        for src in pending:
            cands = _build_candidates_for_source(src)
            logger.info("Zeitplan job {}: source '{}' → {} date candidates",
                        job_id, src.get("filename", src["id"]), len(cands))
            all_candidates.extend(cands)

        if not all_candidates:
            for src in pending:
                db.mark_source_processed(module_id, user_id, src["id"])
            db.update_zeitplan_job(job_id, "success", added_count=0)
            logger.info("Zeitplan job {}: no candidates found", job_id)
            return

        # STAGE 2: ONE batch LLM call classifies everything
        from datetime import date as _date_cls
        today_d = _date_cls.today()
        client, model, _ = _get_llm_client()
        try:
            classifications = _classify_candidates(client, model, all_candidates, today_d)
        except Exception as e:
            logger.error("Zeitplan job {}: classify failed: {}", job_id, e)
            db.update_zeitplan_job(job_id, "failed", error=f"Klassifikation fehlgeschlagen: {e}")
            return

        # STAGE 2b: Deterministic slide-footer override.
        # A date that appears 4+ times in the same single source is almost certainly
        # a slide-deck footer (date printed on every slide), not a real event. Force
        # drop ALL candidates sharing (source_uuid, date). We trust this over the LLM
        # because the LLM only sees ±250 chars of context per candidate and can't see
        # how often the same date repeats across the whole document.
        _SLIDE_FOOTER_THRESHOLD = 4
        from collections import defaultdict
        grp: dict[tuple[str, str], list[int]] = defaultdict(list)
        for idx, cand in enumerate(all_candidates):
            date_key = cand.get("date_iso") or (
                f"partial:{cand['partial_date']}" if cand.get("partial_date") else None
            )
            if date_key is None:
                continue
            grp[(cand["source_uuid"], date_key)].append(idx)
        for (suuid, date_key), indices in grp.items():
            if len(indices) >= _SLIDE_FOOTER_THRESHOLD:
                logger.info(
                    "Zeitplan job {}: slide-footer override — date {} repeats {}x in source {}, dropping all",
                    job_id, date_key, len(indices), suuid,
                )
                for idx in indices:
                    classifications[idx]["keep"] = False
                    classifications[idx]["is_footer"] = True

        # Load existing entries now so the harmonize pass can align new
        # candidate titles with DB entries already present on the same date.
        existing_entries: list[dict] = list(db.get_zeitplan_entries(module_id, user_id))

        # STAGE 2c: Cross-candidate title harmonization for events on the same date.
        # Aligns new candidates with each other AND with existing DB entries so
        # fuzzy-merge downstream picks them up instead of creating duplicates.
        try:
            _harmonize_same_date_titles(
                client, model, all_candidates, classifications, today_d, existing_entries,
            )
        except Exception as e:
            logger.warning("Zeitplan job {}: harmonize pass failed (non-fatal): {}", job_id, e)

        # STAGE 3: Merge into entries (dedup with existing via fuzzy-title + date)
        added = 0

        for cand, cls in zip(all_candidates, classifications):
            if not cls["keep"] or cls["is_footer"] or cls.get("is_historical"):
                logger.info(
                    "Zeitplan job {}: drop candidate date={} (footer={}, historical={}, keep={})",
                    job_id, cand.get("date_iso") or cand.get("partial_date"),
                    cls["is_footer"], cls.get("is_historical"), cls["keep"],
                )
                continue

            # Resolve the date: explicit ISO → use it; partial (MM-DD) → current
            # year; TBD ('nach Vereinbarung') → no date at all.
            if cand.get("is_tbd"):
                due_date_obj = None
            elif cand["date_iso"]:
                due_date_obj = _parse_date(cand["date_iso"])
            elif cand.get("partial_date"):
                mo, da = cand["partial_date"]
                due_date_obj = _resolve_current_year(today_d, mo, da)
            else:
                due_date_obj = None
            # Only non-TBD candidates require a resolved date
            if due_date_obj is None and not cand.get("is_tbd"):
                continue

            ref = {
                "source_uuid": cand["source_uuid"],
                "page_number": cand["page_number"],
                "start_time": cand["start_time"],
                # raw_quote is the short ±80-char snippet used by the frontend
                # highlight search; context (±450) was only for the classifier.
                "raw_quote": cand.get("raw_quote") or cand.get("context"),
            }

            # Try to merge into existing entry (same date + fuzzy title; for TBD:
            # also no-date + fuzzy title).
            merge_target = next(
                (
                    e for e in existing_entries
                    if e.get("due_date") == due_date_obj
                    and _fuzzy_same(cls["title"], e.get("title") or "")
                ),
                None,
            )
            if merge_target:
                db.append_source_ref_to_entry(merge_target["id"], ref)
                # Update local view too, so subsequent candidates see the merge
                merge_target.setdefault("source_refs", []).append(ref)
                logger.info("Zeitplan job {}: merged '{}' into entry #{}",
                            job_id, cls["title"], merge_target["id"])
                continue

            type_ = cls["type"] if cls["type"] in ("deadline", "termin") else "termin"
            new_row = db.create_zeitplan_entry(
                module_id,
                user_id,
                type=type_,
                title=(cls["title"] or cand["date_iso"])[:200],
                description=cls["description"],
                due_date=due_date_obj,
                due_time=_parse_time(cls["due_time"]),
                is_optional=cls["is_optional"],
                origin="llm",
                source_refs=[ref],
            )
            existing_entries.append(new_row)
            added += 1

        # STAGE 4: mark sources processed
        for src in pending:
            db.mark_source_processed(module_id, user_id, src["id"])

        db.update_zeitplan_job(job_id, "success", added_count=added)
        logger.info("Zeitplan job {}: added {} new entries", job_id, added)

    except Exception as e:
        logger.error("Zeitplan job {} failed: {}", job_id, e)
        db.update_zeitplan_job(job_id, "failed", error=str(e))
