"""When a scoped summary should drop to nav-only chips (page/timestamp, no highlight).

Only MEDIA scope (mp3/mp4 — no page numbers) needs nav-only: there is no PDF text
layer to anchor a highlight on, so the chip just scrolls to the timestamp. A multi-PAGE
PDF scope KEEPS highlights now — sentence-tight grounding (C2) marks each bullet's own
sentence on its own page, which is precise, not "wild" across pages.
"""
from src.features.ai_assistant.routes._helpers import _scope_is_nav_only


def _chunk(page=None):
    return {"page_number": page}


def test_media_multi_chunk_is_nav_only():
    # No page numbers (media) + several chunks -> nav-only (no text layer to highlight).
    assert _scope_is_nav_only(set(), [_chunk(), _chunk()]) is True


def test_multi_page_pdf_keeps_highlights():
    # Multiple PDF pages -> NOT nav-only: each bullet gets its tight sentence highlight.
    assert _scope_is_nav_only({14, 15, 16}, [_chunk(14), _chunk(15), _chunk(16)]) is False


def test_single_page_pdf_keeps_highlights():
    assert _scope_is_nav_only({14}, [_chunk(14)]) is False


def test_single_media_chunk_not_nav_only():
    assert _scope_is_nav_only(set(), [_chunk()]) is False


def test_empty_is_not_nav_only():
    assert _scope_is_nav_only(set(), []) is False
