"""KI-Assistent Celery tasks — zeitplan extraction (Regex + Batch-Classify pipeline)."""

import json
import re
from datetime import date, time
from difflib import SequenceMatcher
from typing import Optional

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.tool_prompts import KIA_ZEITPLAN_CLASSIFY_PROMPT
from src.features.ki_assistent.tasks._helpers import _get_llm_client, _clean_llm_json


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
    Language-agnostic.
    """
    ta = set(t for t in _norm_title(a).split() if len(t) >= 3)
    tb = set(t for t in _norm_title(b).split() if len(t) >= 3)
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

_DATE_PATTERNS = [
    # DD.MM.YYYY — requires 4-digit year (prevents 2024 defaulting)
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\b"),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b"),
    # D. Month YYYY (German) — e.g. "15. Juli 2026"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\s+\d{{4}})\b", re.IGNORECASE),
    # Month D, YYYY (English) — e.g. "July 15, 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
]


def _date_candidates_in_text(text: str) -> list[tuple[int, int, str]]:
    """Return list of (start_index, end_index, matched_date_string)."""
    found: list[tuple[int, int, str]] = []
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date")))
    # Deduplicate overlapping matches (prefer the longer span)
    found.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    result: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, d in found:
        if s >= last_end:
            result.append((s, e, d))
            last_end = e
    return result


def _normalize_date(raw: str) -> Optional[str]:
    """Convert a matched date string to ISO 'YYYY-MM-DD'. Returns None on failure."""
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
    # D. Month YYYY (German) / Month D, YYYY (English)
    months = {
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
    m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜüß]+)\s+(\d{4})", s)
    if m:
        d, mo_str, y = m.groups()
        mo = months.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m:
        mo_str, d, y = m.groups()
        mo = months.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    return None


def _build_candidates_for_source(src: dict) -> list[dict]:
    """Find all date candidates in a source. Each candidate carries its position
    (page_number or start_time) and a context window of ±250 chars.
    """
    candidates: list[dict] = []
    for c in _load_source_chunks(src["id"]):
        content = c.get("content") or ""
        if not content:
            continue
        page = c.get("page_number")
        st = c.get("start_time")
        for s, e, raw_date in _date_candidates_in_text(content):
            norm = _normalize_date(raw_date)
            if not norm:
                continue
            ctx_start = max(0, s - 250)
            ctx_end = min(len(content), e + 250)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": raw_date,
                "date_iso": norm,
                "context": ctx,
                "page_number": page,
                "start_time": st,
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })
    return candidates


# ─── Batch classification via single LLM call ──────────────────────────────

_CLASSIFY_BATCH_SIZE = 30  # safe size so a ~10k-token response stays within limits


def _classify_candidates_batch(client, model, batch: list[dict]) -> list[dict]:
    """One LLM call for up to ~30 candidates. Returns classifications aligned to batch order."""
    payload = [
        {
            "id": i,
            "date_raw": c["date_raw"],
            "date_iso": c["date_iso"],
            "context": c["context"],
        }
        for i, c in enumerate(batch)
    ]
    user_msg = (
        "Classify each candidate below. Return a JSON object with key "
        '"results" as an array of the same length (same ids).\n\n'
        "Candidates:\n" + json.dumps(payload, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": KIA_ZEITPLAN_CLASSIFY_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=10000,
        response_format={"type": "json_object"},
    )
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
        out.append({
            "keep": bool(r.get("keep")),
            "is_footer": bool(r.get("is_footer")),
            "type": r.get("type") or "termin",
            "title": (r.get("title") or "").strip(),
            "description": (r.get("description") or None),
            "due_time": (r.get("due_time") or None),
            "is_optional": bool(r.get("is_optional")),
        })
    return out


def _classify_candidates(client, model, candidates: list[dict]) -> list[dict]:
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
        all_results.extend(_classify_candidates_batch(client, model, batch))
    return all_results


# ─── Celery task ───────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="kia.generate_zeitplan", queue="kia",
                 soft_time_limit=300, time_limit=360)
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
        client, model, _ = _get_llm_client()
        try:
            classifications = _classify_candidates(client, model, all_candidates)
        except Exception as e:
            logger.error("Zeitplan job {}: classify failed: {}", job_id, e)
            db.update_zeitplan_job(job_id, "failed", error=f"Klassifikation fehlgeschlagen: {e}")
            return

        # STAGE 3: Merge into entries (dedup with existing via fuzzy-title + date)
        existing_entries: list[dict] = list(db.get_zeitplan_entries(module_id, user_id))
        added = 0

        for cand, cls in zip(all_candidates, classifications):
            if not cls["keep"] or cls["is_footer"]:
                logger.info("Zeitplan job {}: drop candidate date={} reason={}",
                            job_id, cand["date_iso"], cls.get("reason") or "not kept")
                continue

            due_date_obj = _parse_date(cand["date_iso"])
            if due_date_obj is None:
                continue

            ref = {
                "source_uuid": cand["source_uuid"],
                "page_number": cand["page_number"],
                "start_time": cand["start_time"],
                "raw_quote": cand["context"],
            }

            # Try to merge into existing entry (same date + fuzzy title)
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
