"""Tests for per-page OCR retry/backoff in the chunker.

Behaviour contract:
  - Transient errors (429, rate limit, timeout, 5xx) → wait + re-OCR the SAME
    page, up to OCR_MAX_ATTEMPTS times.
  - After retries are exhausted (or on a non-transient error) → raise
    OcrFailedError carrying the page number. The chunker lets this propagate so
    the indexing task marks the source 'failed' (user retries later via the
    existing retry button). Nothing is silently dropped from the index.
"""
import pytest

from src.services.aia_chunker import (
    OCR_MAX_ATTEMPTS,
    OcrFailedError,
    _is_transient_ocr_error,
    _ocr_image_with_retry,
)


class FakeProvider:
    """ocr_image returns/raises the next scripted behaviour per call."""

    def __init__(self, behaviours):
        self._behaviours = list(behaviours)
        self.calls = 0

    def ocr_image(self, image_bytes, mime_type="image/png"):
        b = self._behaviours[self.calls]
        self.calls += 1
        if isinstance(b, Exception):
            raise b
        return b


def _no_sleep(_seconds):
    pass


# ── _is_transient_ocr_error ──────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "Client error '429 Too Many Requests'",
    "Rate limit exceeded",
    "Read timed out",
    "connection timeout",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
])
def test_transient_errors_recognised(msg):
    assert _is_transient_ocr_error(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "400 Bad Request",
    "invalid image payload",
    "401 Unauthorized",
])
def test_non_transient_errors_not_retried(msg):
    assert _is_transient_ocr_error(Exception(msg)) is False


# ── _ocr_image_with_retry ────────────────────────────────────────────────────

def test_success_first_try_no_sleep():
    slept = []
    p = FakeProvider(["page text"])
    out = _ocr_image_with_retry(p, b"png", 7, sleep=lambda s: slept.append(s))
    assert out == "page text"
    assert p.calls == 1
    assert slept == []


def test_transient_then_success_reocrs_same_page():
    slept = []
    p = FakeProvider([Exception("429 Too Many Requests"), "recovered text"])
    out = _ocr_image_with_retry(p, b"png", 3, sleep=lambda s: slept.append(s))
    assert out == "recovered text"
    assert p.calls == 2
    assert len(slept) == 1  # waited once before the successful retry


def test_all_transient_gives_up_and_raises_with_page_number():
    slept = []
    p = FakeProvider([Exception("429")] * OCR_MAX_ATTEMPTS)
    with pytest.raises(OcrFailedError) as exc:
        _ocr_image_with_retry(p, b"png", 42, sleep=lambda s: slept.append(s))
    assert exc.value.page_number == 42
    assert p.calls == OCR_MAX_ATTEMPTS
    assert len(slept) == OCR_MAX_ATTEMPTS - 1  # no sleep after the final attempt


def test_non_transient_fails_fast_without_retrying():
    slept = []
    p = FakeProvider([Exception("400 Bad Request"), "should-not-reach"])
    with pytest.raises(OcrFailedError) as exc:
        _ocr_image_with_retry(p, b"png", 9, sleep=lambda s: slept.append(s))
    assert exc.value.page_number == 9
    assert p.calls == 1          # did not retry a deterministic error
    assert slept == []
