"""Long texts have to be split early, the provider aborts after 60 seconds."""

import pytest

from src.limits import TTS_MAX_CHARS_PER_REQUEST
from src.services.openai_compat_tts import _split_text


def test_short_text_stays_one_request():
    assert _split_text("Guten Morgen.") == ["Guten Morgen."]


def test_screencast_length_script_is_split():
    """1500 to 2000 characters is the normal script length and has to split."""
    script = "Dies ist ein Satz über wissenschaftliches Arbeiten. " * 35  # ~1800 Zeichen
    chunks = _split_text(script)
    assert len(chunks) > 1
    assert all(len(c) <= TTS_MAX_CHARS_PER_REQUEST for c in chunks)


def test_nothing_is_lost_or_duplicated():
    script = "Erster Satz. Zweiter Satz! Dritter Satz? " * 40
    assert "".join(_split_text(script)) == script


def test_splits_at_sentence_ends():
    """Splitting mid-sentence is audible in the recording."""
    script = ("Ein vollständiger Satz mit etwas Länge. " * 30)
    for chunk in _split_text(script)[:-1]:
        assert chunk.rstrip().endswith((".", "!", "?")), f"Schnitt mitten im Satz: {chunk[-40:]!r}"


def test_falls_back_to_word_boundary_without_punctuation():
    """Without punctuation it still must not cut inside a word."""
    script = "Wort " * 300  # keine Satzzeichen
    chunks = _split_text(script)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.endswith(" ") or chunk.endswith("Wort"), f"Schnitt im Wort: {chunk[-12:]!r}"


def test_hard_cut_when_a_single_word_is_longer_than_the_limit():
    """A single overlong word must not trigger an endless loop."""
    chunks = _split_text("A" * (TTS_MAX_CHARS_PER_REQUEST * 3))
    assert len(chunks) == 3
    assert all(len(c) <= TTS_MAX_CHARS_PER_REQUEST for c in chunks)


@pytest.mark.parametrize("limit", [120, 400, 2000])
def test_limit_is_configurable(limit):
    """The limit hangs off the provider and has to be changeable without a rebuild."""
    script = "Ein Satz mit Punkt. " * 200
    chunks = _split_text(script, max_chars=limit)
    assert all(len(c) <= limit for c in chunks)
    assert "".join(chunks) == script
