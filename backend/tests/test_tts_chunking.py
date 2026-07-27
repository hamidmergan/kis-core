"""Zerlegung langer Texte für die Sprachausgabe.

Der Anlass: kein Screencast ließ sich vertonen. Gemessen an THL myLab bricht
jede Anfrage nach genau 60 Sekunden mit HTTP 500 ab. Der Anbieter braucht rund
0,06 bis 0,1 Sekunden je Zeichen, also ist bei etwa 600 Zeichen Schluss.

Zerlegt wurde aber erst ab 10.000 Zeichen. Ein Screencast-Skript hat 1500 bis
2000 Zeichen und ging damit als eine einzige Anfrage raus, die zwangsläufig in
den Timeout lief. Danach folgte der Wiederholungsturm mit 60, 120, 240, 480 und
960 Sekunden Wartezeit.

Das betraf nicht nur den Screencast, sondern jeden Text über etwa 600 Zeichen,
auch im normalen Text-in-Sprache-Werkzeug.
"""

import pytest

from src.limits import TTS_MAX_CHARS_PER_REQUEST
from src.services.openai_compat_tts import _split_text


def test_short_text_stays_one_request():
    assert _split_text("Guten Morgen.") == ["Guten Morgen."]


def test_screencast_length_script_is_split():
    """1500 bis 2000 Zeichen sind die normale Skriptlänge und müssen zerfallen."""
    script = "Dies ist ein Satz über wissenschaftliches Arbeiten. " * 35  # ~1800 Zeichen
    chunks = _split_text(script)
    assert len(chunks) > 1
    assert all(len(c) <= TTS_MAX_CHARS_PER_REQUEST for c in chunks)


def test_nothing_is_lost_or_duplicated():
    script = "Erster Satz. Zweiter Satz! Dritter Satz? " * 40
    assert "".join(_split_text(script)) == script


def test_splits_at_sentence_ends():
    """Mitten im Satz zu trennen hört man in der Aufnahme."""
    script = ("Ein vollständiger Satz mit etwas Länge. " * 30)
    for chunk in _split_text(script)[:-1]:
        assert chunk.rstrip().endswith((".", "!", "?")), f"Schnitt mitten im Satz: {chunk[-40:]!r}"


def test_falls_back_to_word_boundary_without_punctuation():
    """Ohne Satzzeichen darf trotzdem nicht mitten im Wort geschnitten werden."""
    script = "Wort " * 300  # keine Satzzeichen
    chunks = _split_text(script)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.endswith(" ") or chunk.endswith("Wort"), f"Schnitt im Wort: {chunk[-12:]!r}"


def test_hard_cut_when_a_single_word_is_longer_than_the_limit():
    """Ein einzelnes überlanges Wort darf keine Endlosschleife auslösen."""
    chunks = _split_text("A" * (TTS_MAX_CHARS_PER_REQUEST * 3))
    assert len(chunks) == 3
    assert all(len(c) <= TTS_MAX_CHARS_PER_REQUEST for c in chunks)


@pytest.mark.parametrize("limit", [120, 400, 2000])
def test_limit_is_configurable(limit):
    """Die Grenze hängt am Anbieter und muss ohne Neubau änderbar sein."""
    script = "Ein Satz mit Punkt. " * 200
    chunks = _split_text(script, max_chars=limit)
    assert all(len(c) <= limit for c in chunks)
    assert "".join(chunks) == script
