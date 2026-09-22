"""Checks the chunker: transcript merging, file types and extraction."""
import pytest

from src.services.aia_chunker import (
    PdfNoReadableTextError,
    extract_chunks,
    is_media_file,
    segments_to_chunks,
)
from src.services.text_pieces import PIECE_CHARS


# ── segments_to_chunks (Whisper transcript merging) ──────────────────────────

def _seg(start, end, text):
    return {"start": start, "end": end, "text": text}


def test_segments_empty_returns_empty():
    assert segments_to_chunks([]) == []


def test_segments_single_segment_carries_timestamps():
    out = segments_to_chunks([_seg(0.0, 1.5, "hello")])
    assert out == [{
        "page_number": 1,
        "content": "hello",
        "start_time": 0.0,
        "end_time": 1.5,
    }]


def test_segments_short_segments_merge_into_one_chunk():
    out = segments_to_chunks([_seg(0.0, 1.0, "hello"), _seg(1.0, 2.0, "world")])
    assert len(out) == 1
    assert out[0]["content"] == "hello world"
    assert out[0]["start_time"] == 0.0
    assert out[0]["end_time"] == 2.0


def test_segments_skip_empty_text_but_keep_timestamp_anchor():
    out = segments_to_chunks([_seg(0.0, 1.0, "   "), _seg(1.0, 2.0, "hi")])
    assert len(out) == 1
    assert out[0]["content"] == "hi"
    # start_time anchors on the first NON-empty segment.
    assert out[0]["start_time"] == 1.0


def test_segments_overflow_flushes_and_increments_page_number():
    big = "a" * (PIECE_CHARS - 10)
    big2 = "b" * (PIECE_CHARS - 10)
    out = segments_to_chunks([_seg(0.0, 5.0, big), _seg(5.0, 9.0, big2)])
    assert len(out) == 2
    assert out[0]["page_number"] == 1
    assert out[1]["page_number"] == 2
    assert out[0]["content"] == big
    assert out[1]["content"] == big2
    assert out[1]["start_time"] == 5.0


# ── is_media_file ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ft", ["mp3", "mp4", "wav", "flac", "m4a", "webm", ".MP4", "WEBM"])
def test_is_media_file_true_for_audio_video(ft):
    assert is_media_file(ft) is True


@pytest.mark.parametrize("ft", ["pdf", "docx", "pptx", "txt", "md", ".PDF"])
def test_is_media_file_false_for_documents(ft):
    assert is_media_file(ft) is False


# ── extract_chunks dispatch ──────────────────────────────────────────────────

def test_extract_chunks_rejects_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported file_type"):
        extract_chunks("/nonexistent", "xyz")


def test_extract_chunks_rejects_media_with_hint():
    # Audio/video must go through segments_to_chunks, not the file extractor.
    with pytest.raises(ValueError, match="segments_to_chunks"):
        extract_chunks("/nonexistent", "mp3")


# ── _extract_text (plain text / markdown via tmp file) ───────────────────────

def test_extract_text_empty_file_yields_placeholder_page(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    assert extract_chunks(str(f), "txt") == [{"page_number": 1, "content": "[Leere Seite]"}]


def test_extract_text_short_file_single_page(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Title\n\nSome content.", encoding="utf-8")
    chunks = extract_chunks(str(f), "md")
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 1
    assert "Some content." in chunks[0]["content"]


def test_extract_text_long_file_paginates(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * (PIECE_CHARS * 3), encoding="utf-8")
    chunks = extract_chunks(str(f), "txt")
    assert len(chunks) >= 3
    # Page numbers are sequential starting at 1.
    assert [c["page_number"] for c in chunks] == list(range(1, len(chunks) + 1))


def test_pdf_no_readable_text_error_is_a_value_error():
    # The error has to stay a ValueError, otherwise the handling does not catch it.
    assert issubclass(PdfNoReadableTextError, ValueError)
