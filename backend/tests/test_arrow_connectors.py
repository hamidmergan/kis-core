"""Arrows never reach the reader, the rule lives in the code instead of the prompt."""

from src.features.ai_assistant.routes._helpers import _strip_arrow_connectors


def test_arrow_between_sentences_leaves_clean_prose():
    got = _strip_arrow_connectors(
        "Im Passiv wird es zum Subjekt. → Es steht am Anfang."
    )
    assert got == "Im Passiv wird es zum Subjekt. Es steht am Anfang."


def test_ascii_arrows_go_too():
    assert "->" not in _strip_arrow_connectors("Aktiv -> Passiv")
    assert "=>" not in _strip_arrow_connectors("Aktiv => Passiv")
    assert "-->" not in _strip_arrow_connectors("Aktiv --> Passiv")


def test_every_arrow_in_a_line_is_removed():
    got = _strip_arrow_connectors("A. → B. → C.")
    assert "→" not in got
    assert got == "A. B. C."


def test_arrow_at_the_start_of_a_bullet():
    assert _strip_arrow_connectors("- → Hier entfällt es") == "- Hier entfällt es"


def test_line_breaks_survive():
    # The line break has to stay, it closes the line.
    assert _strip_arrow_connectors("Schritt eins\n→ Schritt zwei") == "Schritt eins\n Schritt zwei"


def test_text_without_arrows_is_untouched():
    text = "Die Abgabefrist ist der 3. Juli 2026."
    assert _strip_arrow_connectors(text) == text


def test_a_lone_arrow_token_becomes_a_space():
    # The arrow can arrive as its own chunk, the spaces next to it too.
    assert _strip_arrow_connectors("→") == " "


def test_minus_and_greater_than_in_normal_text_survive():
    assert _strip_arrow_connectors("5 - 3 ist 2") == "5 - 3 ist 2"
    assert _strip_arrow_connectors("a > b") == "a > b"
