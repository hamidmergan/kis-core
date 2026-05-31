"""Tests for the source file-streaming Content-Disposition helper.

Regression guard: a source filename with non-Latin-1 characters (umlauts, or a
combining mark like the NFD "ü" = "u" + U+0308 in "Einführung") must NOT crash
the file endpoint. HTTP headers are latin-1 encoded, so the disposition string
has to stay latin-1 safe (RFC 6266: ASCII `filename` fallback + UTF-8
percent-encoded `filename*`). Before the fix this raised UnicodeEncodeError and
the endpoint returned 500.
"""
import unicodedata

from src.features.ai_assistant.routes.sources._streaming import (
    _inline_content_disposition,
)


def _is_header_safe(value: str) -> bool:
    try:
        value.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def test_disposition_ascii_filename_roundtrips():
    out = _inline_content_disposition("lecture_notes.pdf")
    assert _is_header_safe(out)
    assert 'filename="lecture_notes.pdf"' in out
    assert "filename*=UTF-8''lecture_notes.pdf" in out


def test_disposition_precomposed_umlaut_is_header_safe():
    # NFC "ü" (U+00FC) — still not latin-1? It IS latin-1, but the combining
    # form below is the real-world crash. Cover both.
    name = "Einführung_Skript.pdf"
    out = _inline_content_disposition(name)
    assert _is_header_safe(out)
    assert "filename*=UTF-8''" in out


def test_disposition_combining_diaeresis_is_header_safe():
    # The actual bug: NFD "ü" = "u" + COMBINING DIAERESIS (U+0308), not latin-1.
    name = unicodedata.normalize("NFD", "01_Einführung_WissenschaftlichesSeminar.pdf")
    assert "̈" in name  # sanity: this is the decomposed form
    out = _inline_content_disposition(name)
    # The whole header value must survive latin-1 encoding (else 500).
    assert _is_header_safe(out)
    # ASCII fallback drops the combining mark, keeps the base letters.
    assert 'filename="01_Einfuhrung_WissenschaftlichesSeminar.pdf"' in out
    # filename* carries the real UTF-8 (percent-encoded) for correct display.
    assert "filename*=UTF-8''" in out
    assert "%CC%88" in out  # percent-encoded combining diaeresis


def test_disposition_all_nonascii_name_has_fallback():
    # A name that is entirely non-ASCII still yields a usable fallback.
    out = _inline_content_disposition("中文.pdf")  # "中文.pdf"
    assert _is_header_safe(out)
    assert 'filename="' in out  # fallback present (".pdf" survives)
