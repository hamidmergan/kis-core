"""Welches Whisper-Segment eines Medien-Chunks eine Antwortzeile traegt.

Ein Medien-Chunk fasst bis zu 1000 Zeichen zusammen, gemessen 65 Sekunden im
Schnitt. Der Chip soll auf die Stelle zeigen, an der die zitierte Aussage faellt,
nicht auf den Chunk-Anfang. Welches Segment das ist, entscheidet dieses Modul.

Zwei Regeln, beide an echten Chat-Belegen gemessen (113 bewertbare Faelle aus der
Vorlesungsablage WuK, Wahrheit war: traegt das gewaehlte Segment oder eines der
zwei danach das seltenste Wort der Aussage):

1. **Ein seltenes Wort wiegt mehr als ein haeufiges.** Vorher zaehlte nur, WIE
   VIELE Wortstaemme der Zeile ein Segment traegt. Bei Gleichstand gewann das
   erste, und das war regelmaessig das falsche. Beispiel aus der Messung: zu
   "Die hypergeometrische Verteilung ist ein Modell fuer das ungeordnete Ziehen
   ohne Zuruecklegen, Standardbeispiel Lottospiel" standen im selben Chunk

       25:48  ohne · ziehen · zurueck     <- gewaehlt, sagt "MIT Zuruecklegen"
       26:33  hyperg · vertei · ziehen
       26:46  beispi · lottos · ziehen

   Alle drei mit drei Treffern. "ohne", "ziehen" und "zurueck" stehen hundertfach
   in der Vorlesung, "hyperg" zwoelfmal, "lottos" seltener. Nach Seltenheit
   gewichtet gewinnt die richtige Stelle.

2. **Bewertet wird ein Fenster von drei Segmenten, nicht eines.** Ein
   gesprochener Satz laeuft ueber mehrere Segmente ("Die hypergeometrische
   Verteilung ist ein Modell fuer das Ziehen." / "Ohne Zuruecklegen, ohne
   Beachtung der Reihenfolge." / "Ein Standardbeispiel ist das Lottospielen."),
   und keines davon traegt die Aussage allein. Das Anfangs-Segment zaehlt voll,
   die zwei danach etwas weniger, damit die Zeitmarke am Satzanfang bleibt und
   nicht in einen spaeteren Nachbarn rutscht.

Gemessen, jeweils gegen den Bestand:

    Treffer          63%  ->  77%
    Abstand Median  9,0s  ->  0,0s
    Abstand Mittel 26,3s  -> 16,9s
    besser 16, schlechter 0

Der Abstand ist der zweite, fensterfreie Massstab (Sekunden bis zu dem Segment,
das das seltene Wort wirklich traegt) und damit unabhaengig von der Fensterbreite
oben. Vier und fuenf Segmente Fenster fielen deutlich ab (66% und 64%): drei ist
die Laenge eines gesprochenen Satzes, nicht ein freier Regler.

Die Seltenheit wird ueber die GANZE Quelle gezaehlt, nicht ueber den Chunk. Nur
im Chunk gezaehlt kam die Messung auf 70% statt 77% — unter zwoelf Segmenten
wirkt jedes Wort selten.

Das Modul kennt weder Wortlisten noch Sprachen: Stammbildung und Normalisierung
kommen als Funktionen herein. Deshalb auch keine Rueckrichtung zu ``_helpers``,
die den Import zum Kreis machen wuerde.
"""

import math
from collections import Counter
from typing import Callable, Sequence

# Gewicht der drei Segmente eines Fensters. Der Abfall haelt die Zeitmarke am
# Satzanfang. Gemessen ist der Bereich breit: von 0,80/0,65 bis 1,0/1,0 lagen
# alle Werte bei 76-78% Treffern. Gewaehlt ist das untere Ende des Bereichs, weil
# es als einziges KEINEN Fall verschlechtert hat.
_FENSTER = (1.0, 0.80, 0.65)

# So viele Quellen behalten ihre Seltenheits-Tabelle im Gedaechtnis. Ein Werkzeug
# belegt dutzende Aussagen am Stueck, die auf dieselben paar Quellen zeigen; ohne
# das Gedaechtnis wuerde die Tabelle je Beleg neu ueber alle Segmente gezaehlt.
_CACHE_MAX = 64
_CACHE: dict = {}


def rarity_weights(source_id, segments: Sequence[dict],
                   stems_of: Callable[[str], set],
                   norm: Callable[[str], str]) -> dict:
    """Gewicht je Wortstamm der Quelle: selten schwer, haeufig leicht.

    ``ln(1 + N/(1+df))`` mit N Segmenten und df Segmenten, die den Stamm tragen.
    Ein Stamm in jedem zweiten Segment kommt auf rund 1,1, einer in einem
    einzigen auf ueber 6.

    Gezaehlt wird einmal je Quelle und dann aus dem Gedaechtnis. Ohne
    ``source_id`` (Tests, unzuordenbare Chunks) wird frisch gezaehlt."""
    if not segments:
        return {}
    return _tabellen(source_id, segments, stems_of, norm)[1]


def rare_stems(source_id, segments: Sequence[dict],
               stems_of: Callable[[str], set], norm: Callable[[str], str],
               max_df: int) -> set:
    """Die Wortstaemme, die in hoechstens ``max_df`` Segmenten der Quelle vorkommen."""
    if not segments:
        return set()
    return {stem for stem, anzahl in _tabellen(source_id, segments, stems_of, norm)[0].items()
            if anzahl <= max_df}


def _tabellen(source_id, segments: Sequence[dict],
              stems_of: Callable[[str], set], norm: Callable[[str], str]) -> tuple:
    """Wie viele Segmente jeden Stamm tragen und was er wiegt, einmal je Quelle gezaehlt."""
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
    """Der Segment-Index, an dem die zitierte Aussage anfaengt.

    ``hits_per_segment[i]`` sind die Wortstaemme der Zeile, die Segment ``i``
    traegt. Bewertet wird je Segment das Fenster ab dort; jeder Stamm zaehlt
    einmal, beim ERSTEN Segment des Fensters, in dem er auftaucht.

    ``unbekannt`` ist das Gewicht fuer einen Stamm, den die Tabelle nicht kennt.
    Ohne Angabe das hoechste vorkommende. Das ist kein Notnagel, sondern der
    haeufigere der beiden Faelle: gezaehlt wird ueber die Wortstaemme der
    Segmente, gesucht aber als Zeichenkette IM Segmenttext. "vertei" aus
    "Verteilung" steckt in "Binomialverteilung" drin, ist als eigener Stamm des
    Segments aber nie gezaehlt worden. Beides — echt selten und im Kompositum
    versteckt — heisst unterscheidend, also schwer. Als leicht gewertet fiel die
    Messung von 77% auf 75%.

    Bei echtem Gleichstand gewinnt das fruehere Segment: lieber den Satzanfang
    als seine Mitte. Faengt das beste Fenster mit einem Segment ohne eigenen
    Treffer an, ruecken wir bis zum ersten, das etwas traegt."""
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
