"""Batch-Klassifikation: eine LLM-Anfrage pro ~30 Kandidaten (keep/footer/historical/type/title)."""

import json
import time as _time
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import AIA_SCHEDULE_CLASSIFY_PROMPT


# Classify/harmonize batches can carry up to 30 candidates with ±450 chars of
# context each → responses up to 10k tokens. 120s (OpenAI default) is too tight
# for slower providers; 180s + one retry covers transient stalls.
_CLASSIFY_TIMEOUT_SECS = 180
_CLASSIFY_RETRY_WAIT_SECS = 5

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
                    {"role": "system", "content": AIA_SCHEDULE_CLASSIFY_PROMPT},
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
        logger.info("Schedule classify batch {}/{} ({} candidates)",
                    start // _CLASSIFY_BATCH_SIZE + 1,
                    (n + _CLASSIFY_BATCH_SIZE - 1) // _CLASSIFY_BATCH_SIZE,
                    len(batch))
        all_results.extend(_classify_candidates_batch(client, model, batch, today_d))
    return all_results
