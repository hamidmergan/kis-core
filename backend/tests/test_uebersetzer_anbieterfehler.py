"""A full or disturbed provider makes the translation wait, it does not break the file.

Run 15f, 27.09.: a screencast translation failed for good because the translator turned "provider full" into a ValueError, which counts as permanent.
"""
from io import BytesIO

import httpx
import openai
import pytest
from docx import Document

from src.services.provider_transport import SeatsFull
from src.translators.docx import translate_docx
from src.translators.pptx import translate_pptx
from tests._pptx_fixtures import multi_run_paragraph_pptx

_REQ = httpx.Request("POST", "http://example.invalid")


def _docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Hallo Welt")
    puffer = BytesIO()
    doc.save(puffer)
    return puffer.getvalue()


class _Anbieter:
    def __init__(self, fehler):
        self.fehler = fehler

    def translate_batch(self, texts, source_lang, target_lang):
        raise self.fehler


_UEBERSETZER = [(translate_pptx, multi_run_paragraph_pptx), (translate_docx, _docx)]


@pytest.mark.parametrize("uebersetzen, datei", _UEBERSETZER)
@pytest.mark.parametrize("fehler", [SeatsFull("21:llm", 120), openai.APIConnectionError(request=_REQ)])
def test_ein_fehler_des_anbieters_kommt_unveraendert_durch(uebersetzen, datei, fehler):
    with pytest.raises(type(fehler)):
        uebersetzen(datei(), "DE", "EN-US", _Anbieter(fehler))


@pytest.mark.parametrize("uebersetzen, datei", _UEBERSETZER)
def test_eine_kaputte_datei_bleibt_ein_dateifehler(uebersetzen, datei):
    with pytest.raises(ValueError):
        uebersetzen(b"kein office dokument", "DE", "EN-US", _Anbieter(RuntimeError("nie gefragt")))
