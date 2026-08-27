"""Maps a character position in a media chunk onto the start time of its spot."""

from bisect import bisect_right
from typing import Optional


class TranscriptIndex:
    """The segments of a source, prepared once for positional access."""

    __slots__ = ("_text", "_starts", "_segments")

    def __init__(self, segments: list[dict]):
        texte: list[str] = []
        starts: list[int] = []
        segs: list[dict] = []
        pos = 0
        for s in segments or []:
            t = (s.get("text") or "").strip()
            if not t:                       # das Zerlegen ueberspringt leere Segmente
                continue
            if texte:
                pos += 1                    # das verbindende Leerzeichen
            starts.append(pos)
            pos += len(t)
            texte.append(t)
            segs.append(s)
        self._text = " ".join(texte)
        self._starts = starts
        self._segments = segs

    def __bool__(self) -> bool:
        return bool(self._segments)

    def _basis(self, chunk: dict) -> Optional[int]:
        """Where the chunk text starts in the full transcript, or None."""
        inhalt = (chunk.get("content") or "").strip()
        if not inhalt or not self._text:
            return None
        stellen = []
        i = self._text.find(inhalt)
        while i != -1:
            stellen.append(i)
            i = self._text.find(inhalt, i + 1)
        if not stellen:
            return None
        if len(stellen) == 1:
            return stellen[0]
        ziel = chunk.get("start_time") or 0.0
        return min(stellen, key=lambda p: abs(self._segment_at(p)["start"] - ziel))

    def _segment_at(self, position: int) -> dict:
        """The segment a position in the full transcript falls into."""
        i = bisect_right(self._starts, position) - 1
        return self._segments[max(i, 0)]

    def segments_of(self, chunk: dict) -> list[dict]:
        """The segments this chunk is made of, in their order."""
        if chunk.get("start_time") is None or not self._segments:
            return []
        basis = self._basis(chunk)
        if basis is None:
            return []
        inhalt = (chunk.get("content") or "").strip()
        ende = basis + len(inhalt)
        erstes = max(bisect_right(self._starts, basis) - 1, 0)
        letztes = erstes
        while letztes + 1 < len(self._segments) and self._starts[letztes + 1] < ende:
            letztes += 1
        treffer = self._segments[erstes:letztes + 1]
        gebaut = " ".join((s.get("text") or "").strip() for s in treffer)
        return treffer if gebaut == inhalt else []

    def start_at(self, chunk: dict, offset: int) -> Optional[float]:
        """Start time of the segment speaking at this spot in the chunk text."""
        if chunk.get("start_time") is None or not self._segments:
            return None
        basis = self._basis(chunk)
        if basis is None:
            return None
        laenge = len((chunk.get("content") or "").strip())
        innen = min(max(offset, 0), max(laenge - 1, 0))
        return self._segment_at(basis + innen)["start"]


def start_at_offset(chunk: dict, segments: list[dict], offset: int) -> Optional[float]:
    """Single lookup without an index of its own."""
    return TranscriptIndex(segments).start_at(chunk, offset)
