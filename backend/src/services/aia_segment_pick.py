"""Picks the Whisper segment carrying an answer line, by rarity in a three-segment window."""

import math
from collections import Counter
from typing import Callable, Sequence

# Weight of the three segments of a window, the falloff keeps the mark at the sentence start.
_FENSTER = (1.0, 0.80, 0.65)

# This many sources keep their rarity table in memory.
_CACHE_MAX = 64
_CACHE: dict = {}


def rarity_weights(source_id, segments: Sequence[dict],
                   stems_of: Callable[[str], set],
                   norm: Callable[[str], str]) -> dict:
    """Weight per word stem of the source: rare heavy, common light."""
    if not segments:
        return {}
    return _tabellen(source_id, segments, stems_of, norm)[1]


def rare_stems(source_id, segments: Sequence[dict],
               stems_of: Callable[[str], set], norm: Callable[[str], str],
               max_df: int) -> set:
    """The word stems that occur in at most ``max_df`` segments of the source."""
    if not segments:
        return set()
    return {stem for stem, anzahl in _tabellen(source_id, segments, stems_of, norm)[0].items()
            if anzahl <= max_df}


def _tabellen(source_id, segments: Sequence[dict],
              stems_of: Callable[[str], set], norm: Callable[[str], str]) -> tuple:
    """How many segments carry each stem and what it weighs, counted once per source."""
    n = len(segments)
    schluessel = (source_id, n)
    if source_id is not None and schluessel in _CACHE:
        return _CACHE[schluessel]
    df: Counter = Counter()
    for s in segments:
        text = norm(s.get("text") or "")
        for stem in stems_of(s.get("text") or ""):
            if stem in text:
                df[stem] += 1
    tabellen = (df, {stem: math.log(1.0 + n / (1.0 + anzahl)) for stem, anzahl in df.items()})
    if source_id is not None:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[schluessel] = tabellen
    return tabellen


def best_index(hits_per_segment: Sequence[Sequence[str]], weights: dict,
               unbekannt: float = None) -> int:
    """The segment index where the cited statement begins."""
    if not hits_per_segment:
        return 0
    if unbekannt is None:
        unbekannt = max(weights.values(), default=1.0)
    punkte: list = []
    for i in range(len(hits_per_segment)):
        gesehen: set = set()
        p = 0.0
        for k, gewicht in enumerate(_FENSTER):
            j = i + k
            if j >= len(hits_per_segment):
                break
            for stem in hits_per_segment[j]:
                if stem not in gesehen:
                    gesehen.add(stem)
                    p += weights.get(stem, unbekannt) * gewicht
        punkte.append(p)
    i = max(range(len(punkte)), key=punkte.__getitem__)
    while i < len(hits_per_segment) - 1 and not hits_per_segment[i]:
        i += 1
    return i
