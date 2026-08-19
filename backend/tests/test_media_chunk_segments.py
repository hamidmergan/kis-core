"""Ein Medien-Chunk bekommt seine EIGENEN Segmente, nicht die der Nachbarn.

Die Auswahl lief ueber den Zeitbereich des Chunks. Die gespeicherte Chunk-Startzeit
weicht aber von der Zeit im Transkript-Artefakt ab, gemessen bis zu einer Sekunde,
weil das Artefakt auf ganze Sekunden gerundet ist. Die halbe Sekunde Toleranz fiel
damit auf die falsche Seite und das erste Segment des Chunks fehlte, dafuer rutschten
Segmente des naechsten Chunks herein. An 790 Chunks gemessen traf die Auswahl nur bei
155 den eigenen Chunk-Text.

Das wog doppelt: die Zeitmarke im Chat zeigte auf ein fremdes Segment, und
``_enrich_media_content`` schickte dem Modell den Text der Nachbarn statt den des
Chunks, den die Suche gefunden hatte.

Die Zuordnung laeuft jetzt ueber die Reihenfolge: der Chunk-Text ist ein
zusammenhaengendes Stueck der aneinandergereihten Segmente. Keine Zeitarithmetik,
keine Toleranz.
"""

from src.features.ai_assistant.routes._helpers import (
    _chunk_segments,
    _enrich_media_content,
    _line_segment_start,
)


# Nachgebaut wie im Bestand: das Artefakt rundet auf ganze Sekunden, die Chunk-Zeit
# in der Ablage ist die genaue. Genau diese Luecke riss die alte Auswahl auf.
SEGMENTE = [
    {"start": 0.0, "end": 12.0, "text": "Herzlich willkommen zur heutigen Vorlesung."},
    {"start": 12.0, "end": 23.0, "text": "Wir schauen uns zuerst die Grundlagen an."},
    {"start": 23.0, "end": 40.0, "text": "Ich werde einen Aufgabenblock einstellen."},
    {"start": 40.0, "end": 55.0, "text": "Mal gucken, ob ich das im April schaffe."},
    {"start": 55.0, "end": 70.0, "text": "Der naechste Termin ist dann im Januar."},
    {"start": 70.0, "end": 85.0, "text": "Haben das alle so weit mitgekriegt?"},
]


def _chunk(von: int, bis: int, start_versatz: float = 0.77) -> dict:
    """Ein Chunk aus den Segmenten [von, bis), mit der Rundungsluecke im Bestand."""
    teil = SEGMENTE[von:bis]
    return {
        "id": 100 + von,
        "content": " ".join(s["text"] for s in teil),
        "page_number": von + 1,
        "start_time": teil[0]["start"] + start_versatz,
        "end_time": teil[-1]["end"],
    }


def _rebaut(chunk, segmente=SEGMENTE) -> str:
    return " ".join(s["text"] for s in _chunk_segments(chunk, segmente))


# ── Die Auswahl trifft den eigenen Text ─────────────────────────────────────

def test_jeder_chunk_bekommt_genau_seine_segmente():
    """Ueber alle Schnitte hinweg, nicht an einer Beispielstelle."""
    for von in range(len(SEGMENTE)):
        for bis in range(von + 1, len(SEGMENTE) + 1):
            c = _chunk(von, bis)
            assert _rebaut(c) == c["content"], f"Schnitt [{von}:{bis}] greift daneben"
            assert len(_chunk_segments(c, SEGMENTE)) == bis - von


def test_gerundete_startzeit_verliert_das_erste_segment_nicht():
    """Der Fall aus dem Bestand: Chunk-Zeit 23.77, Segmentzeit 23.0."""
    c = _chunk(2, 5, start_versatz=0.77)
    segs = _chunk_segments(c, SEGMENTE)
    assert segs[0]["text"].startswith("Ich werde einen Aufgabenblock")


def test_keine_nachbarsegmente():
    """Das Segment nach dem Chunk gehoert nicht dazu, auch wenn die Zeit passt."""
    c = _chunk(0, 2)
    texte = [s["text"] for s in _chunk_segments(c, SEGMENTE)]
    assert "Ich werde einen Aufgabenblock einstellen." not in texte


def test_fremder_text_gibt_nichts_zurueck():
    """Deckt sich der Chunk nicht mit dem Transkript, gibt es keine Zuordnung.

    So nach einer Uebersetzung des Transkripts. Lieber nichts als das Falsche."""
    fremd = dict(_chunk(0, 3), content="Ein Text, der so nie gesprochen wurde.")
    assert _chunk_segments(fremd, SEGMENTE) == []


def test_ohne_segmente_und_ohne_zeiten():
    assert _chunk_segments(_chunk(0, 2), []) == []
    assert _chunk_segments(dict(_chunk(0, 2), start_time=None), SEGMENTE) == []


# ── Was das Modell zu lesen bekommt ─────────────────────────────────────────

def test_modell_bekommt_den_text_des_chunks_nicht_den_der_nachbarn():
    c = _chunk(2, 5)
    angereichert = _enrich_media_content(c, SEGMENTE)
    ohne_marken = " ".join(w for w in angereichert.split() if not w.startswith("("))
    assert ohne_marken == c["content"]
    assert "Herzlich willkommen" not in angereichert


def test_modell_bekommt_zeitmarken_je_segment():
    c = _chunk(2, 5)
    angereichert = _enrich_media_content(c, SEGMENTE)
    assert "(00:23)" in angereichert and "(00:55)" in angereichert


def test_unzuordenbarer_chunk_geht_unveraendert_ans_modell():
    fremd = dict(_chunk(0, 3), content="Ein Text, der so nie gesprochen wurde.")
    assert _enrich_media_content(fremd, SEGMENTE) == fremd["content"]


# ── Die Zeitmarke im Chat ───────────────────────────────────────────────────

def test_zeitmarke_zeigt_auf_den_satz_am_chunk_ende():
    """Der zitierte Satz faellt kurz vor Schluss, nicht am Chunk-Anfang."""
    c = _chunk(2, 6)
    zeile = "Der naechste Termin ist dann im Januar."
    assert _line_segment_start(zeile, c, SEGMENTE) == 55.0


def test_zeitmarke_ohne_treffer_bleibt_offen():
    """Traegt kein Segment genug Wortstaemme, gibt es keine geratene Minute."""
    c = _chunk(2, 6)
    assert _line_segment_start("Voellig anderes Thema hier.", c, SEGMENTE) is None


# ── Ein seltenes Wort allein reicht ─────────────────────────────────────────
# Gemeldeter Fall (Quelle 2026-03-23.mp4, Chunk 204213, 32:28 bis 33:56): der Chip zu
# "Du darfst eine handgeschriebene, zweiseitige DIN-A4-Formelsammlung verwenden" zeigte
# auf 32:28, den Chunk-Anfang, wo es um Klausuraufgaben geht. Die Stelle faellt bei 32:48.
# Whisper hatte die Passage in Schnipsel von ein bis drei Sekunden zerlegt, die Aussage
# verteilt sich ueber vier davon, und in keinem stehen zwei der gesuchten Woerter. Das
# Fenster hilft nicht, weil zwischen "Formelsammlung" und "DIN A4" fuenf Segmente liegen.

_FUELL = [{"start": float(i * 10), "end": float(i * 10 + 9), "text": f"Wir rechnen die Aufgabe {i} durch."}
          for i in range(30)]
_PRUEFUNG = [
    {"start": 300.0, "end": 302.0, "text": "So muss das irgendwie funktionieren."},
    {"start": 303.0, "end": 306.0, "text": "Sie koennen einen Taschenrechner benutzen."},
    {"start": 308.0, "end": 312.0, "text": "Eine Formelsammlung, Sie koennen sich eine schreiben."},
    {"start": 313.0, "end": 314.0, "text": "Und mitbringen."},
    {"start": 315.0, "end": 316.0, "text": "Das duerfen Sie."},
    {"start": 318.0, "end": 319.0, "text": "Ja, der ist begrenzt."},
    {"start": 320.0, "end": 321.0, "text": "Jetzt ein DIN A4"},
    {"start": 322.0, "end": 324.0, "text": "Platz, Vor- und Rueckseite."},
]
_QUELLE = _FUELL + _PRUEFUNG
_PRUEFUNGS_CHUNK = {
    "id": 204213, "source_id": None, "page_number": 31,
    "content": " ".join(s["text"] for s in _PRUEFUNG),
    "start_time": 300.0, "end_time": 324.0,
}


def test_ein_seltenes_wort_allein_traegt_die_zeitmarke():
    """Nur "Formelsammlung" passt, und das Wort faellt in der Quelle genau einmal."""
    zeile = "Du darfst eine handgeschriebene, zweiseitige DIN-A4-Formelsammlung verwenden."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) == 308.0


def test_ein_haeufiges_wort_allein_traegt_sie_nicht():
    """Ein Wort aus jedem zweiten Segment zeigt auf nichts, da bleibt der Chunk-Anfang."""
    zeile = "Die Aufgabe wird spaeter noch ausfuehrlich besprochen."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) is None


def test_bindestrich_zaehlt_wie_ein_leerzeichen():
    """Die Antwort schreibt "DIN-A4", das Transkript "DIN A4"."""
    zeile = "Erlaubt ist ein DIN-A4-Blatt, Vor- und Rueckseite."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) == 320.0
