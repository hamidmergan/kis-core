"""Die Aufloesung, mit der eine PDF-Seite an die Bilderkennung geht.

Sie stand auf 200 DPI und kostete stillschweigend Tabellenzellen: im Kursplan zweier
Seminar-PDFs fehlte "25.03.2026, 17:30 Uhr", und damit im Zeitplan ein Termin.

Am 13.08.2026 an derselben Seite durchgemessen, nur die Aufloesung veraendert:
300, 250, 175, 150, 144, 120 und 100 DPI lesen die Zelle, 200 DPI nicht, sechs Laeufe
von sechs. Es ist also weder Tagesform des Dienstes noch "je hoeher desto besser",
sondern genau dieser eine Wert.

Der Test haelt den Wert fest. Die Bilderkennung selbst laesst sich hier nicht pruefen,
die haengt am Dienst, aber die Aufloesung, die rausgeht, schon.
"""

import io
import types

from PIL import Image

from src.services import aia_chunker as mod


class _FakeBitmap:
    def __init__(self, groesse):
        self.groesse = groesse

    def to_pil(self):
        return Image.new("RGB", self.groesse, "white")


class _FakePage:
    """Eine Seite in A4 quer, wie pdfium sie mit 72 DPI misst: 842 x 595 Punkte."""

    def __init__(self):
        self.skalen = []

    def render(self, scale):
        self.skalen.append(scale)
        return _FakeBitmap((int(842 * scale), int(595 * scale)))


def test_seitenbild_geht_mit_150_dpi_raus():
    assert mod._OCR_RENDER_DPI == 150

    page = _FakePage()
    png = mod._render_ocr_png(page, 1)

    assert page.skalen == [150 / 72]
    assert png is not None
    assert Image.open(io.BytesIO(png)).format == "PNG"


def test_200_dpi_ist_verbrannt():
    """Der Wert, der die Tabellenzelle gefressen hat, darf nicht zurueckkommen."""
    assert mod._OCR_RENDER_DPI != 200


def test_ein_fehler_beim_rendern_ueberspringt_nur_diese_seite():
    def kaputt(scale):
        raise RuntimeError("pdfium down")

    page = types.SimpleNamespace(render=kaputt)

    assert mod._render_ocr_png(page, 7) is None
