"""Pins the measured resolution a page is sent to image recognition with."""

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
    """An A4 landscape page as pdfium measures it at 72 DPI: 842 x 595 points."""

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
    """The value that ate the table cell must not come back."""
    assert mod._OCR_RENDER_DPI != 200


def test_ein_fehler_beim_rendern_ueberspringt_nur_diese_seite():
    def kaputt(scale):
        raise RuntimeError("pdfium down")

    page = types.SimpleNamespace(render=kaputt)

    assert mod._render_ocr_png(page, 7) is None
