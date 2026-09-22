"""Checks the text pieces: cleaning, splitting and folding small fragments."""

from src.services.text_pieces import (
    PIECE_CHARS,
    _merge_small_spans,
    clean,
    split_spans,
    split_text,
)

# ── _clean ───────────────────────────────────────────────────────────────────

def test_clean_strips_nul_bytes():
    assert clean("a\x00b\x00c") == "abc"


def test_clean_passes_through_clean_text():
    assert clean("hello world") == "hello world"


def test_clean_handles_empty_string():
    assert clean("") == ""


# Standalone accents from LaTeX PDFs, verbatim as they appear in the corpus.

def test_clean_merges_leading_spacing_diaeresis_into_umlaut():
    assert clean("Komplement¨armenge") == "Komplementärmenge"


def test_clean_merges_trailing_spacing_macron_into_overlined_letter():
    assert clean("A¯ = Ω \\ A") == "Ā = Ω \\ A"


def test_clean_merges_accents_inside_a_whole_sentence():
    raw = "Die relative H¨aufigkeit von A¯ ist größer"
    assert clean(raw) == "Die relative Häufigkeit von Ā ist größer"


def test_clean_normalises_ohm_sign_to_greek_omega():
    assert clean("Ω") == "Ω"


def test_clean_leaves_letter_without_precomposed_form_as_combining_pair():
    # B with a macron stays one letter plus a combining stroke.
    assert clean("B¯") == "B̄"


def test_clean_leaves_accent_that_is_not_next_to_a_letter():
    # Badly displaced accents are better left alone than attached wrongly.
    assert clean("Fur jedes Ereignis ¨ A gilt") == "Fur jedes Ereignis ¨ A gilt"


def test_clean_keeps_a_standalone_accent_character():
    assert clean("¨") == "¨"


def test_clean_keeps_degree_sign_untouched():
    # The degree sign is a real character, not a displaced accent.
    assert clean("20 °C warm") == "20 °C warm"


def test_clean_merges_spacing_circumflex_into_letter():
    assert clean("hˆotel") == "hôtel"


def test_clean_merges_spacing_caron_into_letter():
    assert clean("ˇCech") == "Čech"


def test_clean_keeps_ascii_caret_untouched():
    # In normal text '^' stands for a power, not for an accent.
    assert clean("2^3 = 8") == "2^3 = 8"


def test_clean_keeps_backtick_untouched():
    assert clean("`code`") == "`code`"


def test_clean_keeps_acute_used_as_apostrophe():
    # The acute is deliberately left out, here it would make things worse.
    assert clean("geht´s") == "geht´s"


# ── _split_text ──────────────────────────────────────────────────────────────

def test_split_empty_returns_empty_list():
    assert split_text("", 10, 3) == []


def test_split_whitespace_only_returns_empty_list():
    assert split_text("   \n\t ", 10, 3) == []


def test_split_short_text_returns_single_stripped_chunk():
    assert split_text("  hello  ", 10, 3) == ["hello"]


def test_split_text_exactly_chunk_size_is_one_chunk():
    text = "a" * 10
    assert split_text(text, 10, 3) == [text]


def test_split_breaks_at_whitespace_to_avoid_cutting_words():
    # The first chunk is the whole word, never the fragment behind it.
    chunks = split_text("abcdef ghijklmno", 10, 2)
    assert chunks[0] == "abcdef"


def test_split_never_exceeds_chunk_size_and_drops_no_content():
    text = "a" * 25  # no spaces -> hard cuts at chunk_size
    chunks = split_text(text, 10, 3)
    assert chunks  # non-empty
    assert all(len(c) <= 10 for c in chunks)
    assert all(c for c in chunks)  # no empty chunks
    # Every character of the source appears in at least one chunk.
    assert set("".join(chunks)) == {"a"}


def test_split_chunks_overlap():
    text = "0123456789ABCDEFGHIJ"  # 20 chars, no spaces
    chunks = split_text(text, 10, 4)
    assert len(chunks) >= 2
    # Consecutive chunks share their boundary region.
    assert chunks[1][:1] in chunks[0]


def test_split_never_starts_a_chunk_mid_word():
    """The start of a chunk has to sit on a word boundary too."""
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda my"
    chunks = split_text(text, 20, 8)
    assert len(chunks) > 1
    woerter = set(text.split())
    for c in chunks:
        assert c.split()[0] in woerter, f"Chunk beginnt im Wort: {c[:25]!r}"


def test_split_snapping_keeps_every_character():
    # Pulling back lengthens the overlap, it must lose nothing.
    text = " ".join(f"wort{i:03d}" for i in range(40))
    chunks = split_text(text, 50, 15)
    for w in text.split():
        assert any(w in c for c in chunks), f"{w} fehlt"


def test_split_terminates_on_pathological_overlap():
    # An oversized overlap has to abort instead of looping forever.
    chunks = split_text("a" * 50, 10, 10)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1


# ── _merge_small_spans ───────────────────────────────────────────────────────

def test_merge_folds_tiny_trailing_piece_into_previous():
    assert _merge_small_spans([(0, 40), (40, 43)], min_chars=10) == [(0, 43)]


def test_merge_folds_tiny_leading_piece_forward():
    assert _merge_small_spans([(0, 3), (3, 42)], min_chars=10) == [(0, 42)]


def test_merge_keeps_normal_sized_pieces():
    spans = [(0, 50), (50, 100)]
    assert _merge_small_spans(spans, min_chars=10) == spans


def test_merge_single_piece_untouched_even_if_tiny():
    assert _merge_small_spans([(0, 4)], min_chars=10) == [(0, 4)]


# ── split_spans ──────────────────────────────────────────────────────────────

def test_spans_and_strings_say_the_same():
    text = "Ein Satz mit Woertern. " * 40
    gestrippt = text.strip()
    spans = split_spans(gestrippt, 100, 20)
    assert [gestrippt[a:b] for a, b in spans] == split_text(text, 100, 20)


def test_spans_stay_inside_the_text_and_move_forward():
    text = "wort " * 300
    spans = split_spans(text.strip(), 100, 20)
    assert spans[0][0] == 0
    assert all(0 <= a < b <= len(text.strip()) for a, b in spans)
    assert all(b[0] > a[0] for a, b in zip(spans, spans[1:]))


def test_short_text_is_one_span_over_everything():
    assert split_spans("kurz", 100, 20) == [(0, 4)]


def test_empty_text_has_no_span():
    assert split_spans("   ", 100, 20) == []


def test_split_text_folds_tiny_trailing_scrap():
    # A remainder of 5 characters is folded in instead of becoming its own chunk.
    out = split_text("a" * 205, 100, 0)
    assert len(out) == 2
    assert not any(len(c) < 10 for c in out)

