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
