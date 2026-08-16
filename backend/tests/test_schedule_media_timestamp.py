"""Die Zeitmarke eines Zeitplan-Eintrags zeigt auf die Stelle, an der der Termin faellt.

Ein Medien-Chunk fasst bis zu tausend Zeichen zusammen, gemessen ueber eine Minute
gesprochene Zeit. Der Scanner kennt die genaue Zeichenposition seines Fundes, nahm
als Zeitmarke aber den Anfang des ganzen Chunks. Gemessen an einem echten Eintrag:
"Der naechste Termin ist dann im Januar" faellt bei 29:11, der Zeitplan verwies auf
27:56, und dort wird ueber Einsendeaufgaben im April gesprochen.

Der Chunk-Text ist zeichengleich die aneinandergereihten Whisper-Segmente (an allen
21 Medienquellen der Testablage geprueft). Damit zeigt jede Zeichenposition im Chunk
auf genau ein Segment, und dessen Startzeit ist die gesuchte Marke.
"""

import pytest

from src.features.ai_assistant.tasks.studio.schedule import _candidates as mod
from src.services.aia_transcript_offsets import TranscriptIndex, start_at_offset


# ── Segmente einer erfundenen Aufzeichnung ──────────────────────────────────
# Nachgebaut wie Whisper liefert: kurze Saetze, jeder mit eigener Zeit.
SEGMENTE = [
    {"start": 100.0, "end": 110.0, "text": "Ich werde einen Aufgabenblock einstellen."},
    {"start": 110.0, "end": 120.0, "text": "Mal gucken, vielleicht schaffe ich das."},
    {"start": 120.0, "end": 130.0, "text": "Dann ueber Kombinatorik und die Grundaufgaben."},
    {"start": 130.0, "end": 145.0, "text": "Die Klausur ist am 03.07.2026."},
    {"start": 145.0, "end": 160.0, "text": "Die Sprechstunde laeuft nach Vereinbarung."},
]

# So entsteht der Chunk im Ingest: Segmenttexte mit einem Leerzeichen verbunden.
CHUNK = {
    "id": 1,
    "content": " ".join(s["text"] for s in SEGMENTE),
    "page_number": 17,
    "start_time": SEGMENTE[0]["start"],
    "end_time": SEGMENTE[-1]["end"],
}

QUELLE = {"id": 7, "uuid": "u-7", "filename": "vorlesung.mp4", "file_path": "x/vorlesung.mp4"}


@pytest.fixture
def medien_quelle(monkeypatch):
    """Eine Medienquelle mit einem Chunk und den zugehoerigen Segmenten."""
    monkeypatch.setattr(mod.db, "get_aia_chunks_by_source", lambda sid: [dict(CHUNK)])
    monkeypatch.setattr(mod, "_load_transcript_segments", lambda src: list(SEGMENTE))
    return QUELLE


def _finde(kandidaten, teil):
    treffer = [c for c in kandidaten if teil in (c.get("date_raw") or "")]
    assert treffer, f"kein Kandidat mit {teil!r} in {[c.get('date_raw') for c in kandidaten]}"
    return treffer[0]


# ── Die Zeitmarke am Zeitplan-Eintrag ───────────────────────────────────────

def test_datum_zeigt_auf_sein_segment_statt_auf_den_chunk_anfang(medien_quelle):
    """Das Datum faellt im vierten Segment, also zeigt die Marke dorthin."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    kand = _finde(kandidaten, "03.07.2026")
    assert kand["start_time"] == 130.0, "Zeitmarke steht auf dem Chunk-Anfang statt auf dem Satz"


def test_offener_termin_zeigt_auf_sein_segment(medien_quelle):
    """Auch "nach Vereinbarung" hat eine Stelle, nicht nur der Chunk."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    offen = [c for c in kandidaten if c["is_tbd"]]
    assert offen, "kein offener Termin gefunden"
    assert offen[0]["start_time"] == 145.0


def test_seite_bleibt_wie_sie_war(medien_quelle):
    """Nur die Zeitmarke wandert, die Seitenzahl bleibt unangetastet."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    assert all(c["page_number"] == 17 for c in kandidaten)


def test_pdf_ohne_zeiten_bleibt_unberuehrt(monkeypatch):
    """Eine PDF-Quelle hat keine Zeitmarke und darf auch keine bekommen."""
    seite = {"id": 2, "content": "Abgabe bis 03.07.2026.", "page_number": 4,
             "start_time": None, "end_time": None}
    monkeypatch.setattr(mod.db, "get_aia_chunks_by_source", lambda sid: [seite])
    monkeypatch.setattr(mod, "_load_transcript_segments",
                        lambda src: pytest.fail("PDF darf kein Transkript laden"))
    kandidaten = mod._build_candidates_for_source(
        {"id": 8, "uuid": "u-8", "filename": "plan.pdf", "file_path": "x/plan.pdf"})
    assert _finde(kandidaten, "03.07.2026")["start_time"] is None


# ── Die Abbildung Zeichenposition -> Zeit ───────────────────────────────────

def test_jede_position_trifft_ihr_segment():
    """Ueber den ganzen Chunk hinweg, nicht an einer Beispielstelle."""
    index = TranscriptIndex(SEGMENTE)
    pos = 0
    for seg in SEGMENTE:
        for i in range(len(seg["text"])):
            assert index.start_at(CHUNK, pos + i) == seg["start"], \
                f"Position {pos + i} zeigt nicht auf {seg['start']}"
        pos += len(seg["text"]) + 1      # das verbindende Leerzeichen


def test_position_ausserhalb_wird_eingefangen():
    """Ein zu grosser Wert zeigt auf das letzte Segment, nicht ins Leere."""
    index = TranscriptIndex(SEGMENTE)
    assert index.start_at(CHUNK, 10**6) == SEGMENTE[-1]["start"]
    assert index.start_at(CHUNK, -5) == SEGMENTE[0]["start"]


def test_ohne_passendes_transkript_kein_geratener_wert():
    """Deckt sich der Chunk nicht mit den Segmenten, bleibt es beim Chunk-Anfang.

    Das passiert, wenn das Transkript nach dem Zerlegen neu geschrieben wurde,
    etwa durch eine Uebersetzung. Eine geratene Minute waere schlechter als der
    bekannte Rahmen, deshalb gibt es hier None."""
    fremd = dict(CHUNK, content="Ein voellig anderer Text, der so nie gesprochen wurde.")
    assert start_at_offset(fremd, SEGMENTE, 5) is None


def test_ohne_segmente_kein_wert():
    assert start_at_offset(CHUNK, [], 5) is None


def test_chunk_ohne_zeiten_kein_wert():
    """Eine PDF-Seite hat keine Zeitachse, in die eine Position fallen koennte."""
    assert start_at_offset(dict(CHUNK, start_time=None), SEGMENTE, 5) is None


def test_gleicher_wortlaut_zweimal_nimmt_die_nahe_stelle():
    """Sagt jemand denselben Satz zweimal, entscheidet die Zeit des Chunks."""
    segmente = [
        {"start": 10.0, "end": 20.0, "text": "Das ist wichtig."},
        {"start": 20.0, "end": 30.0, "text": "Ein Zwischensatz."},
        {"start": 30.0, "end": 40.0, "text": "Das ist wichtig."},
    ]
    spaeter = {"content": "Das ist wichtig.", "start_time": 30.0, "end_time": 40.0}
    assert start_at_offset(spaeter, segmente, 0) == 30.0
    frueher = {"content": "Das ist wichtig.", "start_time": 10.0, "end_time": 20.0}
    assert start_at_offset(frueher, segmente, 0) == 10.0


def test_leere_segmente_verschieben_die_rechnung_nicht():
    """Das Zerlegen ueberspringt leere Segmente, die Abbildung muss das auch."""
    segmente = [
        {"start": 5.0, "end": 6.0, "text": "  "},
        {"start": 6.0, "end": 12.0, "text": "Erster Satz."},
        {"start": 12.0, "end": 18.0, "text": "Zweiter Satz."},
    ]
    chunk = {"content": "Erster Satz. Zweiter Satz.", "start_time": 6.0, "end_time": 18.0}
    assert start_at_offset(chunk, segmente, 0) == 6.0
    assert start_at_offset(chunk, segmente, len("Erster Satz. ")) == 12.0
