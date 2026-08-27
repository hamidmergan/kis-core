"""A file name with special characters must not crash the delivery."""
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
    # Cover both spellings of the umlaut, the decomposed one is the real crash.
    name = "Einführung_Skript.pdf"
    out = _inline_content_disposition(name)
    assert _is_header_safe(out)
    assert "filename*=UTF-8''" in out


def test_disposition_combining_diaeresis_is_header_safe():
    # The actual bug: NFD is a letter plus a combining diaeresis, not latin-1.
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
