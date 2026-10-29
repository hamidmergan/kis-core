"""Format, size, quality and style of the image tool, plus the image understanding tasks (rework 29.09.2026)."""

import pytest

from src.features.bild import optionen as o


@pytest.mark.parametrize("format_, groesse, pixel", [
    ("1:1", "mittel", "1024x1024"),
    ("16:9", "klein", "1024x576"),
    ("16:9", "gross", "1920x1088"),
    ("9:16", "mittel", "768x1344"),
    ("3:4", "gross", "1248x1664"),
])
def test_format_und_groesse_geben_feste_pixel(format_, groesse, pixel):
    assert o.pixel(format_, groesse) == pixel


def test_alle_groessen_sind_vielfache_von_16():
    for format_ in o.FORMATE:
        for groesse in o.GROESSEN:
            b, h = map(int, o.pixel(format_, groesse).split("x"))
            assert b % 16 == 0 and h % 16 == 0


@pytest.mark.parametrize("format_, groesse", [("2:1", "mittel"), ("1:1", "riesig")])
def test_unbekannte_werte_gelten_nicht(format_, groesse):
    with pytest.raises(ValueError):
        o.pixel(format_, groesse)


def test_wie_vorlage_haelt_das_seitenverhaeltnis():
    """Portrait format used to be stretched to 1024x1024."""
    b, h = map(int, o.wie_vorlage(900, 1600, "mittel").split("x"))
    assert b % 16 == 0 and h % 16 == 0
    assert abs(b / h - 900 / 1600) < 0.03
    assert 0.9e6 < b * h < 1.2e6


def _flaeche(pixel: str) -> int:
    b, h = map(int, pixel.split("x"))
    return b * h


def test_wie_vorlage_waechst_mit_der_groesse():
    assert _flaeche(o.wie_vorlage(1000, 1000, "gross")) > 3 * _flaeche(o.wie_vorlage(1000, 1000, "klein"))


def test_kleiner_passt_in_1080_und_haelt_das_verhaeltnis():
    """GWDG rejects heights above 1080."""
    assert o.kleiner("1920x1088") == "1904x1072"
    b, h = map(int, o.kleiner("1088x1920").split("x"))
    assert max(b, h) <= 1080 and b % 16 == 0 and h % 16 == 0
    assert o.kleiner("1024x1024") == "1024x1024"


def test_qualitaet_sind_rechenschritte():
    assert o.schritte("entwurf") < o.schritte("standard") < o.schritte("hoch")
    with pytest.raises(ValueError):
        o.schritte("ultra")


def test_ohne_stil_bleibt_die_beschreibung_und_die_schrift_bleibt_draussen():
    text = o.bild_prompt("Ein Apfel auf dem Tisch", "keiner", ohne_schrift=True)
    assert text.startswith("Ein Apfel auf dem Tisch")
    assert o.OHNE_SCHRIFT in text


def test_ein_stil_kommt_vor_die_beschreibung():
    text = o.bild_prompt("Ein Apfel", "skizze", ohne_schrift=False)
    assert "sketch" in text.lower() and "Subject: Ein Apfel" in text
    assert o.OHNE_SCHRIFT not in text


def test_der_thl_stil_kommt_aus_der_praesentationsvorlage():
    assert "vermilion" in o.bild_prompt("x", "thl", ohne_schrift=False)


def test_ein_unbekannter_stil_gilt_nicht():
    with pytest.raises(ValueError):
        o.bild_prompt("x", "kubismus", ohne_schrift=True)


@pytest.mark.parametrize("aufgabe, merkmal", [
    ("beschreiben", "Describe"),
    ("beschreiben", "chart"),
    ("text", "Transcribe"),
])
def test_jede_aufgabe_hat_ihre_anweisung(aufgabe, merkmal):
    text = o.analyse_anweisung(aufgabe, "de", "")
    assert merkmal in text and "Respond in German." in text


def test_jede_anweisung_traegt_die_grundregeln():
    """The general image instruction is dropped for a task, its rules against inventing and dashes stay."""
    text = o.analyse_anweisung("text", "de", "")
    assert "not visible" in text and "semicolons" in text
    assert "same language as the primary text" not in text


def test_die_eigene_frage_steht_in_der_anweisung_und_die_sprache_folgt_der_wahl():
    text = o.analyse_anweisung("frage", "en", "Wie viele Personen?")
    assert "Wie viele Personen?" in text and "Respond in English." in text


@pytest.mark.parametrize("aufgabe", ["alttext", "grafik"])
def test_alternativtext_und_grafik_gibt_es_nicht_mehr(aufgabe):
    with pytest.raises(ValueError):
        o.analyse_anweisung(aufgabe, "de", "")


def test_eine_eigene_frage_ohne_frage_gilt_nicht():
    with pytest.raises(ValueError):
        o.analyse_anweisung("frage", "de", "  ")


def test_ein_panorama_wird_auf_2048_begrenzt():
    """A 4000x400 template would otherwise exceed 3000 px, which providers reject."""
    b, h = map(int, o.wie_vorlage(4000, 400, "mittel").split("x"))
    assert max(b, h) <= 2048 and b % 16 == 0 and h % 16 == 0


def test_eine_normale_vorlage_bleibt_wie_sie_ist():
    assert o.ausgleichen(1600, 900) == (1600, 900, None)


def test_ein_panorama_wird_auf_4_zu_1_aufgefuellt_und_merkt_sich_den_streifen():
    """klein rejects templates above 8:1 ("Aspect ratio too extreme"), seen 29.09.2026 with 4000x400."""
    b, h, zuschnitt = o.ausgleichen(4000, 400)
    assert (b, h) == (4000, 1000)
    assert zuschnitt == {"achse": "hoehe", "anteil": 0.4}


def test_ein_sehr_hohes_bild_wird_in_der_breite_aufgefuellt():
    b, h, zuschnitt = o.ausgleichen(300, 3000)
    assert (b, h) == (750, 3000) and zuschnitt == {"achse": "breite", "anteil": 0.4}
