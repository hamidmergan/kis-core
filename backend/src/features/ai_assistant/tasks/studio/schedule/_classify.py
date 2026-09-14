"""Batch-Klassifikation: eine LLM-Anfrage pro ~30 Kandidaten (keep/footer/historical/type/title)."""

import json
import time as _time
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.tasks.studio.schedule._parse import _parse_date
from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_CLASSIFY_PROMPT


# Generous timeout plus a second attempt, the answers get long.
# A packet of 120 verdicts measured 171 s, a slow provider needs the rest.
_CLASSIFY_TIMEOUT_SECS = 600
_CLASSIFY_RETRY_WAIT_SECS = 5

# Measured: compact verdicts stay correct at 60 and collapse at 120.
_CLASSIFY_BATCH_SIZE = 60


def _dated_month_days(candidates: list[dict], entries: list[dict]) -> set[tuple[int, int]]:
    """All days that are attested somewhere with a year."""
    out: set[tuple[int, int]] = set()
    for c in candidates:
        iso = c.get("date_iso")
        d = _parse_date(iso) if iso else None
        if d:
            out.add((d.month, d.day))
    for e in entries:
        d = e.get("due_date")
        if d:
            out.add((d.month, d.day))
    return out


def _classify_candidates_batch(client, model, batch: list[dict], today_d: date,
                               dated_month_days: set[tuple[int, int]] | None = None,
                               *, _nachfrage: bool = False) -> list[dict]:
    """One LLM call for a packet of candidates, verdicts aligned to the batch order."""
    dated_month_days = dated_month_days or set()
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
            if (mo, da) in dated_month_days:
                item["documented_with_year_elsewhere"] = True
        if c.get("date_precision") == "month":
            item["month_only"] = True
        if c.get("is_tbd"):
            item["date_tbd"] = True
        # The model decides whether the second date really is a span end.
        if c.get("date_end_raw"):
            item["date_end_raw"] = c["date_end_raw"]
            item["date_end_iso"] = c.get("date_end_iso")
        payload.append(item)

    user_msg = (
        f"Current date (today): {today_d.isoformat()}.\n\n"
        "Classify each candidate below. If a candidate has year_missing=true, "
        "the system resolves it to the CURRENT calendar year. "
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
                    {"role": "system", "content": AIA_SCHEDULE_CLASSIFY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=20000,
                response_format={"type": "json_object"},
                timeout=_CLASSIFY_TIMEOUT_SECS,
            )
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                raise
            if "timeout" in err_str.lower() and attempt == 0:
                logger.warning("Schedule classify: timeout, retrying once in {}s", _CLASSIFY_RETRY_WAIT_SECS)
                _time.sleep(_CLASSIFY_RETRY_WAIT_SECS)
                continue
            raise
    raw = (response.choices[0].message.content or "").strip()
    raw = _clean_llm_json(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Schedule-Classify JSON decode failed. Raw tail:\n{}", raw[-2000:])
        raise e

    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        raise ValueError("Classifier did not return a 'results' array")

    by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
    # A forgotten id looks like a dropped one, so it is asked about once more.
    fehlend = [i for i in range(len(batch)) if i not in by_id]
    nachgefragt: dict[int, dict] = {}
    if fehlend and not _nachfrage:
        logger.warning("Schedule classify: {} of {} verdicts missing, asking again",
                       len(fehlend), len(batch))
        zweite = _classify_candidates_batch(client, model, [batch[i] for i in fehlend],
                                            today_d, dated_month_days, _nachfrage=True)
        nachgefragt = dict(zip(fehlend, zweite))
    elif fehlend:
        logger.warning("Schedule classify: {} verdicts still missing, counted as dropped",
                       len(fehlend))
    out: list[dict] = []
    for i in range(len(batch)):
        if i in nachgefragt:
            out.append(nachgefragt[i])
            continue
        r = by_id.get(i) or {}
        keep = bool(r.get("keep"))
        is_footer = bool(r.get("is_footer"))
        is_header = bool(r.get("is_header"))
        is_historical = bool(r.get("is_historical"))
        # Hard-drop header/footer page chrome and historical references
        if is_footer or is_header or is_historical:
            keep = False
        out.append({
            "keep": keep,
            "is_footer": is_footer,
            "is_header": is_header,
            "is_historical": is_historical,
            "type": r.get("type") or "termin",
            "title": (r.get("title") or "").strip(),
            "description": (r.get("description") or None),
            "due_time": (r.get("due_time") or None),
            # Only confirmed spans carry an end.
            "is_range": bool(r.get("is_range")) and bool(batch[i].get("date_end_raw")),
            "end_time": (r.get("end_time") or None),
            "is_open_ended": bool(r.get("is_open_ended")),
            "is_optional": bool(r.get("is_optional")),
        })
    return out


def _classify_candidates(client, model, candidates: list[dict], today_d: date,
                         dated_month_days: set[tuple[int, int]] | None = None) -> list[dict]:
    """Classifies the candidates in batches and returns a flat list."""
    if not candidates:
        return []
    all_results: list[dict] = []
    n = len(candidates)
    for start in range(0, n, _CLASSIFY_BATCH_SIZE):
        batch = candidates[start:start + _CLASSIFY_BATCH_SIZE]
        logger.info("Schedule classify batch {}/{} ({} candidates)",
                    start // _CLASSIFY_BATCH_SIZE + 1,
                    (n + _CLASSIFY_BATCH_SIZE - 1) // _CLASSIFY_BATCH_SIZE,
                    len(batch))
        all_results.extend(
            _classify_candidates_batch(client, model, batch, today_d, dated_month_days)
        )
    return all_results
