"""Which of the fetched pages an answer actually drew on, measured per answer sentence."""
import re
from typing import Callable

from loguru import logger

from src.limits import CAMPUS_SOURCE_MAX_DISTANCE

_LINE_MARK_RE = re.compile(r"^\s*(?:[-*+>#]+|\d+[.)])\s+")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")
_MIN_UNIT_LETTERS = 12


def answer_units(text: str) -> list[str]:
    """Lines and sentences of an answer, list marks and emphasis removed, fragments left out."""
    out: list[str] = []
    for raw in text.split("\n"):
        line = _LINE_MARK_RE.sub("", raw).replace("**", "").strip()
        for unit in _SENTENCE_END_RE.split(line):
            unit = unit.strip()
            if sum(ch.isalpha() for ch in unit) >= _MIN_UNIT_LETTERS:
                out.append(unit)
    return out


def used_sources(
    answer: str,
    sources: list[dict],
    chunk_ids: list[int],
    embed: Callable[[list[str]], list[list[float]]],
    nearest: Callable[[list[float], list[int]], tuple[int, float] | None],
    max_distance: float = CAMPUS_SOURCE_MAX_DISTANCE,
) -> list[dict]:
    """The sources whose page holds the nearest passage of at least one answer sentence, in answer order, none for small talk."""
    units = answer_units(answer)
    if not units or not sources or not chunk_ids:
        return sources
    try:
        vectors = embed(units)
    except Exception as e:  # noqa: BLE001
        logger.warning("Campus: Einbettung der Antwort fehlgeschlagen, alle Fundstellen bleiben Quelle: {}", e)
        return sources
    by_page = {s["page_id"]: s for s in sources}
    picked: list[int] = []
    for vector in vectors:
        hit = nearest(vector, chunk_ids)
        if hit is not None and hit[0] in by_page and hit[1] <= max_distance and hit[0] not in picked:
            picked.append(hit[0])
    return [by_page[pid] for pid in picked]
