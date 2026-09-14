"""Finds appointments whose date is still open, by meaning instead of by pattern."""

import re

# One wording per language the application serves, the search runs once per entry.
QUERIES = (
    "Der Termin wird noch bekannt gegeben, das Datum steht noch nicht fest.",
    "The date will be announced later, the appointment is not fixed yet.",
)
# Room enough for a whole module, the classification sorts the rest out.
_LIMIT_PER_QUERY = 25
# Words that point at an open appointment, they only decide which sentence is quoted.
_MARKERS = frozenset({
    "termin", "termine", "datum", "zeitpunkt", "bekannt", "gegeben", "steht",
    "fest", "folgt", "später", "spaeter", "absprache", "vereinbarung",
    "date", "time", "announced", "announce", "confirmed", "tba", "tbd",
    "appointment", "scheduled", "later", "arranged", "agreed",
})
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def _best_sentence(text: str) -> tuple[int, int, str]:
    """The sentence that talks most about an open appointment, else the first one."""
    best = None
    for m in _SENTENCE.finditer(text):
        satz = m.group().strip()
        if not satz:
            continue
        woerter = {w.strip(".,;:()\u201e\u201c").lower() for w in satz.split()}
        score = len(woerter & _MARKERS)
        if best is None or score > best[0]:
            start = m.start() + (len(m.group()) - len(m.group().lstrip()))
            best = (score, start, start + len(satz), satz)
    if best is None:
        return 0, 0, ""
    _score, start, end, satz = best
    return start, end, satz


def open_spots_for_workspace(workspace_id, source_ids, *, embed, search
                             ) -> dict[int, tuple[int, int, str]]:
    """Per chunk id the spot that reads like an appointment without a date."""
    spots: dict[int, tuple[int, int, str]] = {}
    for query in QUERIES:
        for chunk in search(workspace_id, query, embed(query), source_ids,
                            _LIMIT_PER_QUERY) or []:
            cid = chunk.get("id")
            if cid is None or cid in spots:
                continue
            start, end, phrase = _best_sentence(chunk.get("content") or "")
            if phrase:
                spots[cid] = (start, end, phrase)
    return spots
