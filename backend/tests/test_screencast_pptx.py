"""Text-Extraktion aus PPTX für den Screencast.

Was hier schiefging: SmartArt und Diagramme legen ihren Text nicht in die Folie,
sondern in eigene Teile der Datei (ppt/diagrams/dataN.xml, ppt/charts/chartN.xml).
Die Folie enthält nur einen Verweis. Ein Scan über das Folien-XML findet dort
also nichts, die Folie gilt als leer und bekommt kein Sprechskript.

Versteckte Folien sind der zweite Fallstrick: python-pptx liefert sie mit,
LibreOffice exportiert sie nicht. Zählt die Extraktion sie mit, laufen ab der
ersten versteckten Folie Bild und Ton auseinander.
"""

from tests._pptx_fixtures import (
    CHART_CATEGORIES,
    CHART_TITLE,
    SMARTART_TEXTS,
    chart_pptx,
    hidden_slide_pptx,
    smartart_pptx,
)

from src.services.screencast.pptx import extract_text_per_slide


def test_extracts_plain_textbox():
    texts = extract_text_per_slide(smartart_pptx())
    assert texts[0] == "Normaler Text auf Folie 1"


def test_extracts_smartart_text():
    texts = extract_text_per_slide(smartart_pptx())
    for expected in SMARTART_TEXTS:
        assert expected in texts[1], f"SmartArt-Text fehlt: {expected!r}"


def test_extracts_chart_title_and_categories():
    text = extract_text_per_slide(chart_pptx())[0]
    assert CHART_TITLE in text
    for category in CHART_CATEGORIES:
        assert category in text


def test_chart_numbers_are_not_extracted_as_text():
    """Nur Beschriftungen sind Text. Die Zahlenreihe gehört nicht ins Skript."""
    text = extract_text_per_slide(chart_pptx())[0]
    assert "19.2" not in text
    assert "21.4" not in text


def test_hidden_slides_are_skipped():
    """LibreOffice rendert versteckte Folien nicht, also dürfen sie auch keinen Text liefern."""
    texts = extract_text_per_slide(hidden_slide_pptx())
    assert len(texts) == 2
    assert texts == ["Folie A", "Folie C"]


def test_smartart_text_appears_once_with_real_powerpoint_packaging():
    """PowerPoint legt neben das Diagramm eine gerenderte Ersatzgruppe mit demselben Text.

    Käme beides durch, stünde jede SmartArt-Zeile doppelt im Skript und würde
    zweimal vorgelesen.
    """
    from tests._pptx_fixtures import smartart_with_fallback_pptx

    text = extract_text_per_slide(smartart_with_fallback_pptx())[1]
    assert text.count(SMARTART_TEXTS[0]) == 1
    for expected in SMARTART_TEXTS:
        assert expected in text
