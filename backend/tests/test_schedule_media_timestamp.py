"""The timestamp points at the spot where the appointment is mentioned."""

import pytest

from src.features.ai_assistant.tasks.studio.schedule import _candidates as mod
from src.services.aia_transcript_offsets import TranscriptIndex, start_at_offset


# Segments of an invented recording, built the way Whisper delivers.
SEGMENTE = [
    {"start": 100.0, "end": 110.0, "text": "Ich werde einen Aufgabenblock einstellen."},
    {"start": 110.0, "end": 120.0, "text": "Mal gucken, vielleicht schaffe ich das."},
    {"start": 120.0, "end": 130.0, "text": "Dann ueber Kombinatorik und die Grundaufgaben."},
    {"start": 130.0, "end": 145.0, "text": "Die Klausur ist am 03.07.2026."},
    {"start": 145.0, "end": 160.0, "text": "Die Sprechstunde laeuft nach Vereinbarung."},
]

# This is how the chunk arises during ingest: segment texts joined by a space.
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
    """A media source with one chunk and the matching segments."""
    monkeypatch.setattr(mod.db, "get_aia_chunks_by_source", lambda sid: [dict(CHUNK)])
    monkeypatch.setattr(mod, "_load_transcript_segments", lambda src: list(SEGMENTE))
    return QUELLE


def _finde(kandidaten, teil):
    treffer = [c for c in kandidaten if teil in (c.get("date_raw") or "")]
    assert treffer, f"kein Kandidat mit {teil!r} in {[c.get('date_raw') for c in kandidaten]}"
    return treffer[0]


# ── The timestamp on the schedule entry ─────────────────────────────────────

def test_datum_zeigt_auf_sein_segment_statt_auf_den_chunk_anfang(medien_quelle):
    """The date falls in the fourth segment, so the mark points there."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    kand = _finde(kandidaten, "03.07.2026")
    assert kand["start_time"] == 130.0, "Zeitmarke steht auf dem Chunk-Anfang statt auf dem Satz"


def test_offener_termin_zeigt_auf_sein_segment(medien_quelle):
    """An open appointment has a spot too, not just the chunk."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    offen = [c for c in kandidaten if c["is_tbd"]]
    assert offen, "kein offener Termin gefunden"
    assert offen[0]["start_time"] == 145.0


def test_seite_bleibt_wie_sie_war(medien_quelle):
    """Only the timestamp moves, the page number stays untouched."""
    kandidaten = mod._build_candidates_for_source(medien_quelle)
    assert all(c["page_number"] == 17 for c in kandidaten)


def test_pdf_ohne_zeiten_bleibt_unberuehrt(monkeypatch):
    """A PDF source has no timestamp and must not get one."""
    seite = {"id": 2, "content": "Abgabe bis 03.07.2026.", "page_number": 4,
             "start_time": None, "end_time": None}
    monkeypatch.setattr(mod.db, "get_aia_chunks_by_source", lambda sid: [seite])
    monkeypatch.setattr(mod, "_load_transcript_segments",
                        lambda src: pytest.fail("PDF darf kein Transkript laden"))
    kandidaten = mod._build_candidates_for_source(
        {"id": 8, "uuid": "u-8", "filename": "plan.pdf", "file_path": "x/plan.pdf"})
    assert _finde(kandidaten, "03.07.2026")["start_time"] is None


# ── The mapping from character position to time ─────────────────────────────

def test_jede_position_trifft_ihr_segment():
    """Across the whole chunk, not at one sample spot."""
    index = TranscriptIndex(SEGMENTE)
    pos = 0
    for seg in SEGMENTE:
        for i in range(len(seg["text"])):
            assert index.start_at(CHUNK, pos + i) == seg["start"], \
                f"Position {pos + i} zeigt nicht auf {seg['start']}"
        pos += len(seg["text"]) + 1      # das verbindende Leerzeichen


def test_position_ausserhalb_wird_eingefangen():
    """An oversized value points at the last segment, not into nothing."""
    index = TranscriptIndex(SEGMENTE)
    assert index.start_at(CHUNK, 10**6) == SEGMENTE[-1]["start"]
    assert index.start_at(CHUNK, -5) == SEGMENTE[0]["start"]


def test_ohne_passendes_transkript_kein_geratener_wert():
    """Without coverage it stays at the chunk start, a guessed minute would be worse."""
    fremd = dict(CHUNK, content="Ein voellig anderer Text, der so nie gesprochen wurde.")
    assert start_at_offset(fremd, SEGMENTE, 5) is None


def test_ohne_segmente_kein_wert():
    assert start_at_offset(CHUNK, [], 5) is None


def test_chunk_ohne_zeiten_kein_wert():
    """A PDF page has no timeline a position could fall into."""
    assert start_at_offset(dict(CHUNK, start_time=None), SEGMENTE, 5) is None


def test_gleicher_wortlaut_zweimal_nimmt_die_nahe_stelle():
    """If someone says the same sentence twice, the chunk time decides."""
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
    """Chunking skips empty segments, the mapping has to do the same."""
    segmente = [
        {"start": 5.0, "end": 6.0, "text": "  "},
        {"start": 6.0, "end": 12.0, "text": "Erster Satz."},
        {"start": 12.0, "end": 18.0, "text": "Zweiter Satz."},
    ]
    chunk = {"content": "Erster Satz. Zweiter Satz.", "start_time": 6.0, "end_time": 18.0}
    assert start_at_offset(chunk, segmente, 0) == 6.0
    assert start_at_offset(chunk, segmente, len("Erster Satz. ")) == 12.0
