"""Checks the text recognition run per document: open pages, shutdown, report."""
import pytest

from src.services.aia_chunker import OCR_MAX_FAILED_PAGES, _OcrRun


class FakeProvider:
    """ocr_image plays back the next scripted behaviour per call."""

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
    # One page fails, the next runs again, no abort.
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

    # Third candidate: never touched, but still counted as open.
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
    # The threshold is part of the contract, not just of the code.
    assert OCR_MAX_FAILED_PAGES == 2
