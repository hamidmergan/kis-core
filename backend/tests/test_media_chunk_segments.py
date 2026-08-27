"""A media chunk gets its own segments, matched up by their order."""

from src.features.ai_assistant.routes._helpers import (
    _chunk_segments,
    _enrich_media_content,
    _line_segment_start,
)


# The artefact rounds to whole seconds, the chunk time is exact.
SEGMENTE = [
    {"start": 0.0, "end": 12.0, "text": "Herzlich willkommen zur heutigen Vorlesung."},
    {"start": 12.0, "end": 23.0, "text": "Wir schauen uns zuerst die Grundlagen an."},
    {"start": 23.0, "end": 40.0, "text": "Ich werde einen Aufgabenblock einstellen."},
    {"start": 40.0, "end": 55.0, "text": "Mal gucken, ob ich das im April schaffe."},
    {"start": 55.0, "end": 70.0, "text": "Der naechste Termin ist dann im Januar."},
    {"start": 70.0, "end": 85.0, "text": "Haben das alle so weit mitgekriegt?"},
]


def _chunk(von: int, bis: int, start_versatz: float = 0.77) -> dict:
    """A chunk from the segments [from, to), with the rounding gap seen in the corpus."""
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


# ── The selection hits its own text ─────────────────────────────────────────

def test_jeder_chunk_bekommt_genau_seine_segmente():
    """Across all cuts, not at one sample spot."""
    for von in range(len(SEGMENTE)):
        for bis in range(von + 1, len(SEGMENTE) + 1):
            c = _chunk(von, bis)
            assert _rebaut(c) == c["content"], f"Schnitt [{von}:{bis}] greift daneben"
            assert len(_chunk_segments(c, SEGMENTE)) == bis - von


def test_gerundete_startzeit_verliert_das_erste_segment_nicht():
    """The case from the corpus: chunk time 23.77, segment time 23.0."""
    c = _chunk(2, 5, start_versatz=0.77)
    segs = _chunk_segments(c, SEGMENTE)
    assert segs[0]["text"].startswith("Ich werde einen Aufgabenblock")


def test_keine_nachbarsegmente():
    """The segment after the chunk does not belong to it, even when the time fits."""
    c = _chunk(0, 2)
    texte = [s["text"] for s in _chunk_segments(c, SEGMENTE)]
    assert "Ich werde einen Aufgabenblock einstellen." not in texte


def test_fremder_text_gibt_nichts_zurueck():
    """Without coverage there is no match, better nothing than the wrong thing."""
    fremd = dict(_chunk(0, 3), content="Ein Text, der so nie gesprochen wurde.")
    assert _chunk_segments(fremd, SEGMENTE) == []


def test_ohne_segmente_und_ohne_zeiten():
    assert _chunk_segments(_chunk(0, 2), []) == []
    assert _chunk_segments(dict(_chunk(0, 2), start_time=None), SEGMENTE) == []


# ── What the model gets to read ─────────────────────────────────────────────

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


# ── The timestamp in the chat ───────────────────────────────────────────────

def test_zeitmarke_zeigt_auf_den_satz_am_chunk_ende():
    """The cited sentence falls shortly before the end, not at the chunk start."""
    c = _chunk(2, 6)
    zeile = "Der naechste Termin ist dann im Januar."
    assert _line_segment_start(zeile, c, SEGMENTE) == 55.0


def test_zeitmarke_ohne_treffer_bleibt_offen():
    """If no segment carries enough word stems, there is no guessed minute."""
    c = _chunk(2, 6)
    assert _line_segment_start("Voellig anderes Thema hier.", c, SEGMENTE) is None


# One rare word is enough when the statement is spread over many snippets.

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
    """Only one word fits, and it occurs exactly once in the source."""
    zeile = "Du darfst eine handgeschriebene, zweiseitige DIN-A4-Formelsammlung verwenden."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) == 308.0


def test_ein_haeufiges_wort_allein_traegt_sie_nicht():
    """A word from every other segment points at nothing, so the chunk start stays."""
    zeile = "Die Aufgabe wird spaeter noch ausfuehrlich besprochen."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) is None


def test_bindestrich_zaehlt_wie_ein_leerzeichen():
    """The answer writes 'DIN-A4', the transcript 'DIN A4'."""
    zeile = "Erlaubt ist ein DIN-A4-Blatt, Vor- und Rueckseite."
    assert _line_segment_start(zeile, _PRUEFUNGS_CHUNK, _QUELLE) == 320.0
