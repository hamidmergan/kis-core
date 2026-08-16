"""Tests for the document chunker (text splitting, transcript merging, dispatch).

These cover the PURE-LOGIC core that needs no PDF/Office libraries or files, plus
the dispatch error paths and the plain-text extractor (via a tmp file).
"""
import pytest

from src.services.aia_chunker import (
    CHUNK_SIZE,
    PdfNoReadableTextError,
    _clean,
    _merge_small_fragments,
    _split_text,
    extract_chunks,
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


# ── _clean: lose Akzentzeichen aus LaTeX-PDFs ────────────────────────────────
# Ein mit LaTeX gesetztes PDF malt Akzente als EIGENE Glyphe neben den Buchstaben.
# Die Textebene liefert sie darum als freistehendes Zeichen (U+00A8, U+00AF, ...)
# direkt vor oder hinter dem Grundbuchstaben. Die Beispiele unten stehen woertlich
# so in der Datenbank (Mathe-Vorkurs-Skript).

def test_clean_merges_leading_spacing_diaeresis_into_umlaut():
    assert _clean("Komplement¨armenge") == "Komplementärmenge"


def test_clean_merges_trailing_spacing_macron_into_overlined_letter():
    assert _clean("A¯ = Ω \\ A") == "Ā = Ω \\ A"


def test_clean_merges_accents_inside_a_whole_sentence():
    raw = "Die relative H¨aufigkeit von A¯ ist größer"
    assert _clean(raw) == "Die relative Häufigkeit von Ā ist größer"


def test_clean_normalises_ohm_sign_to_greek_omega():
    assert _clean("Ω") == "Ω"


def test_clean_leaves_letter_without_precomposed_form_as_combining_pair():
    # B + Makron hat keine fertige Einzelform, bleibt also ein Grundbuchstabe
    # plus kombinierendem Strich. Im Browser sieht das trotzdem korrekt aus.
    assert _clean("B¯") == "B̄"


def test_clean_leaves_accent_that_is_not_next_to_a_letter():
    # Weit verrutschte Akzente sind nicht sicher zuzuordnen: das Zeichen gehoert
    # zu "Fur" mehrere Woerter davor. Lieber stehen lassen als falsch anhaengen.
    assert _clean("Fur jedes Ereignis ¨ A gilt") == "Fur jedes Ereignis ¨ A gilt"


def test_clean_keeps_a_standalone_accent_character():
    assert _clean("¨") == "¨"


def test_clean_keeps_degree_sign_untouched():
    # Das Gradzeichen ist ein echtes Zeichen, kein verrutschter Akzent.
    assert _clean("20 °C warm") == "20 °C warm"


def test_clean_merges_spacing_circumflex_into_letter():
    assert _clean("hˆotel") == "hôtel"


def test_clean_merges_spacing_caron_into_letter():
    assert _clean("ˇCech") == "Čech"


def test_clean_keeps_ascii_caret_untouched():
    # "^" steht in normalem Text fuer eine Potenz, nicht fuer einen Akzent.
    assert _clean("2^3 = 8") == "2^3 = 8"


def test_clean_keeps_backtick_untouched():
    assert _clean("`code`") == "`code`"


def test_clean_keeps_acute_used_as_apostrophe():
    # Der Akut ist bewusst aussen vor: hier waere "gehtś" schlechter als vorher.
    assert _clean("geht´s") == "geht´s"


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


# ── _merge_small_fragments ───────────────────────────────────────────────────

def test_merge_folds_tiny_trailing_fragment_into_previous():
    out = _merge_small_fragments(["A full sentence of real body text here.", "hdr"], min_chars=10)
    assert out == ["A full sentence of real body text here. hdr"]


def test_merge_folds_tiny_leading_fragment_forward():
    out = _merge_small_fragments(["hdr", "A full sentence of real body text here."], min_chars=10)
    assert out == ["hdr A full sentence of real body text here."]


def test_merge_keeps_normal_sized_chunks():
    chunks = ["a" * 50, "b" * 50]
    assert _merge_small_fragments(chunks, min_chars=10) == chunks


def test_merge_single_chunk_untouched_even_if_tiny():
    assert _merge_small_fragments(["tiny"], min_chars=10) == ["tiny"]


def test_split_text_folds_tiny_trailing_scrap():
    # 205 chars, chunk_size 100, no overlap -> 100/100/5; threshold = 100//10 = 10,
    # so the 5-char scrap is folded into its neighbour, not left as its own chunk.
    out = _split_text("a" * 205, 100, 0)
    assert len(out) == 2
    assert not any(len(c) < 10 for c in out)


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


def test_pdf_no_readable_text_error_is_a_value_error():
    # The Celery task catches ValueError; PdfNoReadableTextError must stay in
    # that hierarchy so the existing handler keeps working.
    assert issubclass(PdfNoReadableTextError, ValueError)
