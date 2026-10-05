"""One model call per packet: the hit blocks go in, only the real appointments come back."""

import json
import re
import time as _time
from datetime import date

from loguru import logger

from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_EXTRACT_PROMPT
from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.tasks.studio.schedule._parse import _parse_date
from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text

_TIMEOUT_SECS = 600
_RETRY_WAIT_SECS = 20
# Room for a few hundred appointments, measured: 600k chars of dense text plus this still fit the window.
_MAX_TOKENS = 16000
# Text kept around the quote for the browser search and the title harmonisation.
_CONTEXT_RADIUS = 200
_WS = re.compile(r"\s+")


class AnswerTruncated(ValueError):
    """The model stopped at its answer cap, so the JSON it sent is incomplete."""


def hit_blocks(src: dict, chunks: list[dict], open_spots: dict) -> list[dict]:
    """The chunks of a source with a date pattern or an open-appointment spot, as blocks."""
    blocks: list[dict] = []
    for c in chunks:
        text = c.get("content") or ""
        if not text.strip():
            continue
        if c.get("id") not in open_spots and not _date_candidates_in_text(text):
            continue
        blocks.append({
            "id": c["id"],
            "text": text,
            "source_id": src["id"],
            "source_uuid": src["uuid"],
            "source_filename": src.get("filename") or "",
            "page_number": c.get("page_number"),
            "start_time": c.get("start_time"),
            "chunk": c,
        })
    return blocks


def packets(blocks: list[dict], max_chars: int) -> list[list[dict]]:
    """Greedy packets in block order, one source per packet, an oversize block travels alone."""
    out: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for b in blocks:
        n = len(b["text"])
        # A shared packet lets the model name a repeated date for one source only.
        if current and (size + n > max_chars or b["source_id"] != current[-1]["source_id"]):
            out.append(current)
            current, size = [], 0
        current.append(b)
        size += n
    if current:
        out.append(current)
    return out


# Measured: the provider runs two big requests side by side, a third slows all of them.
_PARALLEL_BIG = 2
# Small requests cost mostly answer time, several of them share the provider well.
_PARALLEL_SMALL = 6
# From this size on, inputs running side by side drag the provider down.
_BIG_PACKET_CHARS = 100_000


def parallel_packets(pakete: list[list[dict]]) -> int:
    """How many packets run side by side, big inputs keep it at two."""
    groesste = max((sum(len(b["text"]) for b in p) for p in pakete), default=0)
    return _PARALLEL_BIG if groesste >= _BIG_PACKET_CHARS else _PARALLEL_SMALL


def extract_packet(client, model, packet: list[dict], today: date) -> list[dict]:
    """One request for one packet, a packet the provider rejects goes again in two halves."""
    try:
        return _extract_once(client, model, packet, today)
    except Exception as e:
        abgeschnitten = isinstance(e, AnswerTruncated)
        if not (abgeschnitten or "400" in str(e)) or len(packet) < 2:
            raise
        mitte = len(packet) // 2
        logger.warning("Terminsuche: Paket mit {} Bloecken {}, geht in zwei Haelften",
                       len(packet), "zu lang beantwortet" if abgeschnitten else "abgewiesen")
        return (extract_packet(client, model, packet[:mitte], today)
                + extract_packet(client, model, packet[mitte:], today))


def _extract_once(client, model, packet: list[dict], today: date) -> list[dict]:
    """One request for one packet, returns the raw appointment items with their block ids."""
    payload = [{"id": b["id"], "text": b["text"]} for b in packet]
    user_msg = (
        f"Current date (today): {today.isoformat()}.\n\n"
        "Return every real appointment or deadline in the blocks below, most blocks hold "
        "none.\n\nBlocks:\n" + json.dumps(payload, ensure_ascii=False)
    )
    response = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AIA_SCHEDULE_EXTRACT_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=_MAX_TOKENS,
                response_format={"type": "json_object"},
                timeout=_TIMEOUT_SECS,
            )
            break
        except Exception as e:
            if "timeout" in str(e).lower() and attempt == 0:
                logger.warning("Terminsuche: Zeitueberschreitung, ein Versuch in {}s",
                               _RETRY_WAIT_SECS)
                _time.sleep(_RETRY_WAIT_SECS)
                continue
            raise
    if getattr(response.choices[0], "finish_reason", None) == "length":
        raise AnswerTruncated(
            f"Terminsuche: Antwort abgeschnitten, Paket mit {len(packet)} Bloecken")
    raw = _clean_llm_json((response.choices[0].message.content or "").strip())
    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise ValueError("Terminsuche lieferte kein JSON-Objekt")
    items = parsed.get("appointments") or []
    return [i for i in items if isinstance(i, dict)]


def _year_written(year: int, text: str) -> bool:
    """Does the text write this year, in full or as the short year of a numeric date?"""
    if re.search(rf"(?<!\d){year}(?!\d)", text):
        return True
    return bool(re.search(rf"\d{{1,2}}[./-]\d{{1,2}}[./-]{year % 100:02d}(?!\d)", text))


def _date_parts(value, text: str | None = None) -> tuple[str | None, tuple[int, int] | None, str] | None:
    """One of the four date shapes as iso, partial and precision, a year missing from the text is dropped."""
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        if not _parse_date(s):
            return None
        # The model fills in years despite the rule, the quoted spot decides.
        if text is not None and not _year_written(int(m.group(1)), text):
            return None, (int(m.group(2)), int(m.group(3))), "day"
        return s, None, "day"
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if not 1 <= mo <= 12:
            return None
        if text is not None and not _year_written(y, text):
            return None, (mo, 1), "month"
        return f"{y:04d}-{mo:02d}-01", None, "month"
    m = re.fullmatch(r"(\d{2})-(\d{2})", s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return (None, (mo, d), "day") if 1 <= mo <= 12 and 1 <= d <= 31 else None
    # A month without a year sorts on its first day once the year rule has run.
    m = re.fullmatch(r"(\d{2})", s)
    if m:
        mo = int(m.group(1))
        return (None, (mo, 1), "month") if 1 <= mo <= 12 else None
    return None


def _locate(text: str, quote: str) -> tuple[int, str] | None:
    """Offset of the quote in the block and the text around it, None when it is not there."""
    norm_text = _WS.sub(" ", text)
    norm_quote = _WS.sub(" ", quote).strip()
    if not norm_quote:
        return None
    # The model likes to lower the first letter, the text decides the case.
    i = norm_text.casefold().find(norm_quote.casefold())
    if i < 0:
        return None
    ctx = norm_text[max(0, i - _CONTEXT_RADIUS):i + len(norm_quote) + _CONTEXT_RADIUS].strip()
    exact = text.find(quote)
    return (exact if exact >= 0 else i), ctx


def items_to_pairs(items: list[dict], blocks: list[dict], today: date,
                   time_at=None) -> dict[int, tuple[list[dict], list[dict]]]:
    """The model's appointments as (candidate, verdict) pairs per source, every source present."""
    by_id = {b["id"]: b for b in blocks}
    out: dict[int, tuple[list[dict], list[dict]]] = {}
    for b in blocks:
        out.setdefault(b["source_id"], ([], []))
    for item in items:
        b = by_id.get(item.get("id"))
        if b is None:
            logger.info("Terminsuche: unbekannte Blocknummer {!r}, verworfen", item.get("id"))
            continue
        quote = str(item.get("quote") or "")
        spot = _locate(b["text"], quote)
        if spot is None:
            logger.info("Terminsuche: Zitat nicht im Block, verworfen: {!r}", quote[:80])
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            logger.info("Terminsuche: Termin ohne Titel, verworfen: {!r}", quote[:80])
            continue
        start = item.get("date")
        parts = _date_parts(start, quote) if start not in (None, "") else (None, None, "day")
        if parts is None:
            logger.info("Terminsuche: unlesbares Datum {!r}, verworfen", start)
            continue
        iso, partial, precision = parts
        end = item.get("end_date")
        end_parts = _date_parts(end, quote) if end not in (None, "") else None
        if end not in (None, "") and end_parts is None:
            logger.info("Terminsuche: unlesbares Enddatum {!r}, wird ignoriert", end)
        end_iso, end_partial = (end_parts[0], end_parts[1]) if end_parts else (None, None)
        offset, ctx = spot
        st = time_at(b, offset) if time_at else b.get("start_time")
        type_ = item.get("type") if item.get("type") in ("deadline", "termin") else "termin"
        cands, cls = out[b["source_id"]]
        cands.append({
            "date_raw": quote,
            "date_iso": iso,
            "partial_date": partial,
            "date_precision": precision,
            "date_end_raw": str(end) if end_parts else None,
            "date_end_iso": end_iso,
            "date_end_partial": end_partial,
            "is_tbd": iso is None and partial is None,
            "context": ctx,
            "raw_quote": quote,
            "page_number": b.get("page_number"),
            "start_time": st,
            "source_uuid": b["source_uuid"],
            "source_filename": b["source_filename"],
        })
        cls.append({
            "keep": True,
            "is_footer": False,
            "is_header": False,
            "is_historical": False,
            "type": type_,
            "title": title,
            "description": (str(item.get("description")).strip() or None)
            if item.get("description") else None,
            "due_time": item.get("time") or None,
            "end_time": item.get("end_time") or None,
            "is_range": end_parts is not None,
            "is_open_ended": bool(item.get("open_ended")) and end_parts is None,
            "is_optional": bool(item.get("optional")),
        })
    return out
