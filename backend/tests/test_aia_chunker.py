"""Tests for the document chunker (text splitting, transcript merging, structural-page
detection, dispatch).

These cover the PURE-LOGIC core that needs no PDF/Office libraries or files, plus
the dispatch error paths and the plain-text extractor (via a tmp file). The
structural-page heuristic is checked in BOTH German and English to guard the
language-agnostic requirement: the TOC/references skip must never depend on a
single language's word list.
"""
import pytest

from src.services.aia_chunker import (
    CHUNK_SIZE,
    PdfNoReadableTextError,
    _clean,
    _is_structural_page,
    _split_text,
    extract_chunks,
    get_page_count,
    is_media_file,
    segments_to_chunks,
)


# ── _clean ───────────────────────────────────────────────────────────────────

def test_clean_strips_nul_bytes():
    assert _clean("a\x00b\x00c") == "abc"


def test_clean_passes_through_clean_text():
    assert _clean("hello world") == "hello world"


def test_clean_handles_empty_string():
    assert _clean("") == ""


# ── _split_text ──────────────────────────────────────────────────────────────

def test_split_empty_returns_empty_list():
    assert _split_text("", 10, 3) == []


def test_split_whitespace_only_returns_empty_list():
    assert _split_text("   \n\t ", 10, 3) == []


def test_split_short_text_returns_single_stripped_chunk():
    assert _split_text("  hello  ", 10, 3) == ["hello"]


def test_split_text_exactly_chunk_size_is_one_chunk():
    text = "a" * 10
    assert _split_text(text, 10, 3) == [text]


def test_split_breaks_at_whitespace_to_avoid_cutting_words():
    # chunk_size 10: first window is "abcdef ghi"; the space at index 6 (> 10//2)
    # triggers a break, so the first chunk is the whole word "abcdef", never "ghi".
    chunks = _split_text("abcdef ghijklmno", 10, 2)
    assert chunks[0] == "abcdef"


def test_split_never_exceeds_chunk_size_and_drops_no_content():
    text = "a" * 25  # no spaces -> hard cuts at chunk_size
    chunks = _split_text(text, 10, 3)
    assert chunks  # non-empty
    assert all(len(c) <= 10 for c in chunks)
    assert all(c for c in chunks)  # no empty chunks
    # Every character of the source appears in at least one chunk.
    assert set("".join(chunks)) == {"a"}


def test_split_chunks_overlap():
    text = "0123456789ABCDEFGHIJ"  # 20 chars, no spaces
    chunks = _split_text(text, 10, 4)
    assert len(chunks) >= 2
    # Consecutive chunks share their boundary region (overlap), so the tail of
    # chunk N reappears at the head of chunk N+1.
    assert chunks[1][:1] in chunks[0]


def test_split_terminates_on_pathological_overlap():
    # overlap >= chunk_size would make next_start regress; the guard must break
    # instead of looping forever.
    chunks = _split_text("a" * 50, 10, 10)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1


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
    big = "a" * (CHUNK_SIZE - 10)
    big2 = "b" * (CHUNK_SIZE - 10)
    out = segments_to_chunks([_seg(0.0, 5.0, big), _seg(5.0, 9.0, big2)])
    assert len(out) == 2
    assert out[0]["page_number"] == 1
    assert out[1]["page_number"] == 2
    assert out[0]["content"] == big
    assert out[1]["content"] == big2
    assert out[1]["start_time"] == 5.0


# ── _is_structural_page (TOC / references detection) ──────────────────────────

@pytest.mark.parametrize("heading", [
    "Table of Contents",
    "Contents",
    "Inhaltsverzeichnis",
    "References",
    "Bibliography",
    "Literaturverzeichnis",
    "Quellenverzeichnis",
    "List of Figures",
    "Abbildungsverzeichnis",
])
def test_structural_page_detects_keyword_first_line_any_language(heading):
    # Language-agnostic: both German and English structural headings must trip
    # the skip, case-insensitively.
    assert _is_structural_page([{"content": heading}]) is True
    assert _is_structural_page([{"content": heading.upper()}]) is True


def test_structural_page_keyword_must_be_whole_first_line():
    # A heading word embedded in a sentence is NOT a structural page.
    assert _is_structural_page([{"content": "References are listed below"}]) is False


def test_structural_page_detects_dotted_toc_lines():
    blocks = [
        {"content": "Introduction ......... 1"},
        {"content": "Methods .............. 12"},
        {"content": "Results .............. 23"},
    ]
    assert _is_structural_page(blocks) is True


def test_structural_page_two_dotted_lines_not_enough():
    blocks = [
        {"content": "Introduction ......... 1"},
        {"content": "Methods .............. 12"},
        {"content": "A normal paragraph of body text."},
    ]
    assert _is_structural_page(blocks) is False


def test_structural_page_normal_content_is_not_structural():
    blocks = [
        {"content": "Chapter 1: Background"},
        {"content": "This study examines the effect of X on Y."},
    ]
    assert _is_structural_page(blocks) is False


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
    f.write_text("x" * (CHUNK_SIZE * 3), encoding="utf-8")
    chunks = extract_chunks(str(f), "txt")
    assert len(chunks) >= 3
    # Page numbers are sequential starting at 1.
    assert [c["page_number"] for c in chunks] == list(range(1, len(chunks) + 1))


def test_get_page_count_matches_chunk_count(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("y" * (CHUNK_SIZE * 2), encoding="utf-8")
    assert get_page_count(str(f), "txt") == len(extract_chunks(str(f), "txt"))


def test_pdf_no_readable_text_error_is_a_value_error():
    # The Celery task catches ValueError; PdfNoReadableTextError must stay in
    # that hierarchy so the existing handler keeps working.
    assert issubclass(PdfNoReadableTextError, ValueError)
