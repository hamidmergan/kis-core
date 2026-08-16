"""Zeichenposition in einem Medien-Chunk -> Startzeit der Stelle.

Ein Medien-Chunk fasst bis zu tausend Zeichen Transkript zusammen. Wie lang das in
Minuten wird, haengt allein am Sprechtempo, gemessen ueber eine Minute im Schnitt.
Wer im Chunk-Text etwas findet, kennt die Zeichenposition seines Fundes, hatte als
Zeitmarke aber nur den Anfang des ganzen Chunks. Damit zeigt der Verweis im
schlimmsten Fall zwei Minuten vor die Stelle, die gemeint ist.

Das Zerlegen (``aia_chunker.segments_to_chunks``) reiht die Whisper-Segmente in
ihrer Reihenfolge aneinander, verbunden durch ein Leerzeichen, und schneidet nach
Zeichenzahl. Der Chunk-Text ist deshalb ein zusammenhaengendes Stueck aus dem
aneinandergereihten Transkript, Zeichen fuer Zeichen (an allen 21 Medienquellen der
Testablage geprueft: 165.000 Zeichen je Quelle, kein Unterschied). Also laesst sich
der Chunk darin wiederfinden und jede Position darin auf genau ein Segment abbilden.

Bewusst NICHT ueber den Zeitbereich des Chunks: Whisper-Segmente ueberlappen sich in
der Zeit, eine Auswahl ueber ``start_time``/``end_time`` greift daneben und zieht
Nachbarsegmente herein. An denselben Quellen gemessen traf sie nur bei 155 von 790
Chunks den eigenen Text.

Findet sich der Chunk nicht wieder, gibt es keinen Wert. Das passiert, wenn das
Transkript nach dem Zerlegen neu geschrieben wurde, etwa durch eine Uebersetzung.
Eine geratene Minute waere schlechter als der bekannte Rahmen, also faellt der
Aufrufer auf den Chunk-Anfang zurueck.

Sprachunabhaengig: gerechnet wird mit Positionen, nicht mit Wortlisten.
"""

from bisect import bisect_right
from typing import Optional


class TranscriptIndex:
    """Die Segmente einer Quelle, einmal fuer den Positions-Zugriff aufbereitet.

    Ein Werkzeug fragt dutzende Fundstellen derselben Quelle ab. Einmal bauen und
    dann behalten spart das wiederholte Zusammensetzen des Gesamttextes.
    """

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
        """Wo der Chunk-Text im Gesamttranskript beginnt, oder None.

        Kommt derselbe Wortlaut mehrfach vor (ein wiederholter Satz, ein kurzer
        Chunk), entscheidet die Zeit: genommen wird die Fundstelle, deren Segment
        dem gespeicherten Chunk-Anfang am naechsten liegt."""
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
        """Das Segment, in das eine Position im Gesamttranskript faellt."""
        i = bisect_right(self._starts, position) - 1
        return self._segments[max(i, 0)]

    def segments_of(self, chunk: dict) -> list[dict]:
        """Die Segmente, aus denen dieser Chunk besteht, in ihrer Reihenfolge.

        Leer, wenn sich der Chunk nicht im Transkript wiederfindet. Der Rueckgabewert
        wird gegen den Chunk-Text geprueft: was nicht Wort fuer Wort zusammenpasst,
        gilt als nicht zugeordnet. Sonst koennte fremder Text als Inhalt des Chunks
        durchgehen."""
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
        """Startzeit des Segments, das an ``offset`` im Chunk-Text spricht.

        ``offset`` ist eine Position im Chunk-Text selbst. Werte ausserhalb werden
        auf den Chunk eingefangen, damit ein Aufrufer mit einer Spanne am Textende
        nicht ins Leere greift. None heisst: nicht zuzuordnen, nimm den
        Chunk-Anfang."""
        if chunk.get("start_time") is None or not self._segments:
            return None
        basis = self._basis(chunk)
        if basis is None:
            return None
        laenge = len((chunk.get("content") or "").strip())
        innen = min(max(offset, 0), max(laenge - 1, 0))
        return self._segment_at(basis + innen)["start"]


def start_at_offset(chunk: dict, segments: list[dict], offset: int) -> Optional[float]:
    """Einzelabfrage ohne eigenen Index. Fuer wiederholte Fragen an dieselbe
    Quelle stattdessen einen :class:`TranscriptIndex` bauen und behalten."""
    return TranscriptIndex(segments).start_at(chunk, offset)
