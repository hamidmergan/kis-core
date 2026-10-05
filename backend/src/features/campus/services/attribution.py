"""Which of the fetched pages an answer actually drew on, measured per answer sentence."""
import re
from typing import Callable

from loguru import logger

from src.limits import CAMPUS_SOURCE_MAX_DISTANCE, CAMPUS_SOURCE_MIN_RARE_WORDS

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
    word_pages: Callable[[str, list[int]], dict[int, set[str]]] | None = None,
    max_distance: float = CAMPUS_SOURCE_MAX_DISTANCE,
) -> list[dict]:
    """The sources whose page holds the nearest passage or else the rare words of at least one answer sentence, in answer order, none for small talk."""
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
    for unit, vector in zip(units, vectors):
        hit = nearest(vector, chunk_ids)
        page = hit[0] if hit is not None and hit[1] <= max_distance else None
        if page is None and word_pages is not None:
            page = _page_by_words(word_pages(unit, chunk_ids))
        if page in by_page and page not in picked:
            picked.append(page)
    return [by_page[pid] for pid in picked]


def _page_by_words(words: dict[int, set[str]]) -> int | None:
    """The page holding enough rare words of a sentence that no other fetched page holds, if there is exactly one."""
    own: dict[int, int] = {}
    for pid, held in words.items():
        others = set().union(*(w for p, w in words.items() if p != pid))
        own[pid] = len(held - others)
    leaders = [pid for pid, n in own.items() if n >= CAMPUS_SOURCE_MIN_RARE_WORDS]
    return leaders[0] if len(leaders) == 1 else None
