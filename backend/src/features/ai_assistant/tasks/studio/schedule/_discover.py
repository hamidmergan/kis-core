"""Finds open appointments and spelled-out dates in any language via the model."""

import json
import re
import time as _time
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.upstream_errors import is_provider_refusal
from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_TBD_DISCOVER_PROMPT


# Characters sent per request.
_MAX_CHARS_PER_CALL = 100000
_MAX_BLOCKS_PER_CALL = 120
# A single block that is out of line must not blow up the request.
_MAX_BLOCK_CHARS = 4000
# The answers here are short, 180 s is only for a slow provider.
_TIMEOUT_SECS = 180
_RETRY_WAIT_SECS = 5
# Shorter blocks cannot carry an announcement.
_MIN_BLOCK_CHARS = 15
# The model should name the spot, not return half the block.
_MAX_PHRASE_CHARS = 120
# No chunk has more spelled-out dates, anything above is running wild.
_MAX_DATES_PER_BLOCK = 6

# The three precisions a spelled-out date may come back in.
_DATE_FULL = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DATE_DAY_MONTH = re.compile(r"^(\d{2})-(\d{2})$")


def _parse_model_date(value: str) -> dict | None:
    """Translates the model's numeric form into our candidate fields."""
    value = (value or "").strip()

    m = _DATE_FULL.match(value)
    if m:
        jahr, monat, tag = int(m[1]), int(m[2]), int(m[3])
        try:
            date(jahr, monat, tag)
        except ValueError:
            return None
        return {"date_iso": f"{jahr:04d}-{monat:02d}-{tag:02d}",
                "partial_date": None, "date_precision": "day"}

    m = _DATE_MONTH.match(value)
    if m:
        jahr, monat = int(m[1]), int(m[2])
        if not 1 <= monat <= 12:
            return None
        return {"date_iso": f"{jahr:04d}-{monat:02d}-01",
                "partial_date": None, "date_precision": "month"}

    m = _DATE_DAY_MONTH.match(value)
    if m:
        monat, tag = int(m[1]), int(m[2])
        if not (1 <= monat <= 12 and 1 <= tag <= 31):
            return None
        return {"date_iso": None, "partial_date": [monat, tag], "date_precision": "day"}

    return None


def _locate(content: str, phrase: str) -> tuple[int, int] | None:
    """Finds the named spot again in the block text, otherwise the hit is discarded."""
    phrase = (phrase or "").strip()
    if not phrase or len(phrase) > _MAX_PHRASE_CHARS:
        return None
    pos = content.find(phrase)
    if pos != -1:
        return pos, pos + len(phrase)
    pos = content.lower().find(phrase.lower())
    if pos != -1:
        return pos, pos + len(phrase)
    tokens = [re.escape(t) for t in phrase.split()]
    if not tokens:
        return None
    m = re.search(r"\s+".join(tokens), content, re.IGNORECASE)
    if m:
        return m.start(), m.end()
    return None


def _batches(blocks: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Bundles blocks into requests, bounded by character count and number."""
    out: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    chars = 0
    for bid, text in blocks:
        if current and (len(current) >= _MAX_BLOCKS_PER_CALL
                        or chars + len(text) > _MAX_CHARS_PER_CALL):
            out.append(current)
            current = []
            chars = 0
        current.append((bid, text))
        chars += len(text)
    if current:
        out.append(current)
    return out


def _discover_batch(client, model, batch: list[tuple[int, str]]) -> dict[int, dict]:
    """One request, two yields per block: the open spot and the date hits."""
    payload = [{"id": bid, "text": text} for bid, text in batch]
    user_msg = (
        "Two jobs on the blocks below.\n"
        '"results": places where a real event has no fixed date yet, at most one per '
        "block.\n"
        '"dates": dates written out in words, in any language, with their digit form. '
        "Numeric dates are handled elsewhere, skip them.\n"
        "Blocks with nothing to report are left out of an array, both arrays may be "
        "empty.\n\n"
        "Blocks:\n" + json.dumps(payload, ensure_ascii=False)
    )
    response = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AIA_SCHEDULE_TBD_DISCOVER_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=8000,
                response_format={"type": "json_object"},
                timeout=_TIMEOUT_SECS,
            )
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                raise
            if "timeout" in err_str.lower() and attempt == 0:
                logger.warning("Terminsuche: Zeitueberschreitung, ein Versuch in {}s",
                               _RETRY_WAIT_SECS)
                _time.sleep(_RETRY_WAIT_SECS)
                continue
            raise

    raw = _clean_llm_json((response.choices[0].message.content or "").strip())
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Terminsuche lieferte kein JSON-Objekt")
    # An empty object is a valid answer, it means this packet holds nothing.
    results = parsed.get("results")
    dates = parsed.get("dates")

    valid_ids = {bid for bid, _ in batch}
    found: dict[int, dict] = {bid: {"tbd": None, "dates": []} for bid, _ in batch}

    for r in results if isinstance(results, list) else []:
        if not isinstance(r, dict):
            continue
        bid = r.get("id")
        phrase = r.get("phrase") if isinstance(r.get("phrase"), str) else ""
        phrase = (phrase or "").strip()
        if bid not in valid_ids or not phrase or found[bid]["tbd"]:
            continue
        found[bid]["tbd"] = phrase

    for r in dates if isinstance(dates, list) else []:
        if not isinstance(r, dict):
            continue
        bid = r.get("id")
        phrase = r.get("phrase") if isinstance(r.get("phrase"), str) else ""
        phrase = (phrase or "").strip()
        wert = r.get("date") if isinstance(r.get("date"), str) else ""
        if bid not in valid_ids or not phrase:
            continue
        if len(found[bid]["dates"]) >= _MAX_DATES_PER_BLOCK:
            continue
        felder = _parse_model_date(wert)
        if felder is None:
            logger.info("Terminsuche: unbrauchbare Ziffernform {!r} zu {!r}", wert, phrase)
            continue
        found[bid]["dates"].append({"phrase": phrase, **felder})

    return found


def _discover_in_blocks(client, model, blocks: list[tuple[int, str]]) -> dict[int, dict]:
    """Has the blocks searched, an error stays without consequence for the job."""
    if client is None:
        return {}
    usable: list[tuple[int, str]] = []
    truncated = 0
    for bid, text in blocks:
        if len(text.strip()) < _MIN_BLOCK_CHARS:
            continue
        if len(text) > _MAX_BLOCK_CHARS:
            truncated += 1
        usable.append((bid, text[:_MAX_BLOCK_CHARS]))
    if truncated:
        logger.warning("Terminsuche: {} Bloecke auf {} Zeichen gekuerzt",
                       truncated, _MAX_BLOCK_CHARS)
    if not usable:
        return {}

    batches = _batches(usable)

    found: dict[int, dict] = {}
    for i, batch in enumerate(batches):
        try:
            found.update(_discover_batch(client, model, batch))
        except Exception as e:  # noqa: BLE001 - the schedule is built even without this search
            if "429" in str(e) or is_provider_refusal(e):
                logger.warning("Terminsuche: Anfrage {}/{} abgewiesen, Quelle wird abgebrochen: {}",
                               i + 1, len(batches), e)
                break
            # One bad packet must not cost the pages behind it.
            logger.warning("Terminsuche: Anfrage {}/{} fehlgeschlagen, wird uebersprungen: {}",
                           i + 1, len(batches), e)
            continue
    offene = sum(1 for v in found.values() if v["tbd"])
    daten = sum(len(v["dates"]) for v in found.values())
    logger.info("Terminsuche: {} Bloecke in {} Anfragen, {} offene Stellen, {} Daten",
                len(usable), len(batches), offene, daten)
    return found
