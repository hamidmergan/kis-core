"""The pure rendering pieces of the trace script, without touching Langfuse or job storage."""

from scripts.summary_trace import (
    _aufruf_abschnitt,
    _dauer,
    _fakten_tabelle,
    _gliederung_abschnitt,
    _quellen_tabelle,
)


def test_quellen_tabelle_zeigt_typ_seiten_und_zeichen():
    tabelle = _quellen_tabelle([
        {"filename": "a.pdf", "ext": "pdf", "pages": 12, "content": "x" * 500},
        {"filename": "b.txt", "ext": "txt", "pages": None, "content": "y" * 10},
    ])
    assert "| a.pdf | pdf | 12 | 500 |" in tabelle
    assert "| b.txt | txt | - | 10 |" in tabelle


def test_fakten_tabelle_zaehlt_je_datei():
    tabelle = _fakten_tabelle({"doc_01": [{}, {}], "doc_02": [{}]})
    assert "| doc_01 | 2 |" in tabelle
    assert "| doc_02 | 1 |" in tabelle


def test_gliederung_ohne_speicherung_sagt_das():
    assert "Einzelaufruf" in _gliederung_abschnitt(None, {})


def test_gliederung_zeigt_abdeckung_und_abschnitte():
    outline = {"intro": "Vorweg.", "sections": [
        {"title": "A", "description": "erstens", "fact_ids": [1, 2]},
        {"title": "B", "description": "zweitens", "fact_ids": [3]}]}
    text = _gliederung_abschnitt(outline, {"doc_01": [{}, {}, {}]})
    assert "3 von 3 Fakten zugeordnet" in text
    assert "**A** (2 Fakten): erstens" in text
    assert "**B** (1 Fakten): zweitens" in text


def test_dauer_rechnet_die_differenz():
    aufruf = {"startTime": "2026-09-19T16:10:15.000Z", "endTime": "2026-09-19T16:10:17.500Z"}
    assert _dauer(aufruf) == "2.5 s"


def test_dauer_ohne_zeiten_ist_unbekannt():
    assert _dauer({}) == "unbekannt"


def test_aufruf_abschnitt_zeigt_system_nutzer_und_antwort():
    aufruf = {
        "name": "read:doc_01", "model": "m", "startTime": "2026-09-19T16:00:00.000Z",
        "endTime": "2026-09-19T16:00:02.000Z",
        "modelParameters": {"temperature": 0.1, "max_tokens": 3000},
        "metadata": {"response_format": {"json_schema": {"name": "facts"}}},
        "promptTokens": 100, "completionTokens": 50,
        "input": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "NUTZER"}],
        "output": "ANTWORT",
    }
    text = _aufruf_abschnitt(1, aufruf)
    assert "## Aufruf 1: read:doc_01" in text
    assert "Schema: `facts`" in text
    assert "SYS" in text and "NUTZER" in text and "ANTWORT" in text


def test_aufruf_abschnitt_ohne_antwort_zeigt_leer():
    aufruf = {"input": [], "output": None}
    assert "(leer)" in _aufruf_abschnitt(1, aufruf)
