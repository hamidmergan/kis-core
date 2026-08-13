"""Tests fuer den OCR-Lauf pro Dokument (_OcrRun).

Verhaltensvertrag:
  - Eine Seite, die nicht durchkommt, killt das Dokument NICHT mehr. Sie behaelt
    ihre Textebene und wird als offen vermerkt.
  - Nach OCR_MAX_FAILED_PAGES gescheiterten Seiten wird die Texterkennung fuer
    den Rest des Dokuments abgeschaltet. Der Backoff ist der teure Teil, und ein
    Dienst, der zwei Seiten hintereinander verliert, ist weg und nicht busy.
  - Der Bericht sagt der Oberflaeche, ob Texterkennung lief, wie viele Seiten
    fertig sind und welche noch offen sind. None heisst: gar kein Kandidat.
"""
import pytest

from src.services.aia_chunker import OCR_MAX_FAILED_PAGES, _OcrRun


class FakeProvider:
    """ocr_image spielt pro Aufruf das naechste Skript-Verhalten ab."""

    def __init__(self, behaviours):
        self._behaviours = list(behaviours)
        self.calls = 0

    def ocr_image(self, image_bytes, mime_type="image/png"):
        b = self._behaviours[self.calls]
        self.calls += 1
        if isinstance(b, Exception):
            raise b
        return b


def _run(behaviours):
    return _OcrRun(FakeProvider(behaviours), sleep=lambda _s: None)


def test_no_candidate_page_reports_nothing():
    run = _OcrRun(FakeProvider([]), sleep=lambda _s: None)
    assert run.report() is None


def test_clean_run_reports_every_page_done():
    run = _run(["Seite eins", "Seite zwei"])
    assert run.wants(1) is True
    assert run.ocr_page(b"png", 1) == "Seite eins"
    assert run.wants(2) is True
    assert run.ocr_page(b"png", 2) == "Seite zwei"
    assert run.report() == {"enabled": True, "done": 2, "open": []}


def test_single_failure_keeps_ocr_running_for_the_rest():
    # Eine Seite faellt aus, die naechste laeuft wieder. Kein Abbruch.
    run = _run([Exception("400 Bad Request"), "Seite zwei"])
    run.wants(1)
    assert run.ocr_page(b"png", 1) == ""
    assert run.wants(2) is True
    assert run.ocr_page(b"png", 2) == "Seite zwei"
    assert run.report() == {"enabled": True, "done": 1, "open": [1]}


def test_gives_up_after_two_failed_pages_and_stops_calling_the_provider():
    provider = FakeProvider([Exception("429")] * 20)
    run = _OcrRun(provider, sleep=lambda _s: None)
    for page in (1, 2):
        assert run.wants(page) is True
        assert run.ocr_page(b"png", page) == ""
    calls_after_giving_up = provider.calls

    # Dritter Kandidat: wird gar nicht mehr angefasst, zaehlt aber als offen.
    assert run.wants(3) is False
    assert provider.calls == calls_after_giving_up
    assert run.report() == {"enabled": True, "done": 0, "open": [1, 2, 3]}


def test_ocr_off_books_every_candidate_as_open():
    run = _OcrRun(None, sleep=lambda _s: None)
    assert run.wants(4) is False
    assert run.wants(9) is False
    assert run.report() == {"enabled": False, "done": 0, "open": [4, 9]}


def test_unrendered_page_counts_as_open_without_touching_the_provider():
    provider = FakeProvider([])
    run = _OcrRun(provider, sleep=lambda _s: None)
    run.wants(5)
    run.mark_open(5)
    assert provider.calls == 0
    assert run.report() == {"enabled": True, "done": 0, "open": [5]}


def test_give_up_threshold_is_two():
    # Die Schwelle steht im Vertrag, nicht nur im Code: ein Dokument darf hoechstens
    # zweimal auf den Backoff warten, bevor Texterkennung fuer den Rest ausgeht.
    assert OCR_MAX_FAILED_PAGES == 2
