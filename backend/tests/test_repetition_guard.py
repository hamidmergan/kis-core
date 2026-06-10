"""Safety net against a model repetition/degeneration loop — when the LLM gets stuck
emitting the same few bullets over and over (seen with 'fasse detailliert zusammen'
on a thin source). Two pieces:

  * _RepetitionGuard  — fed each completed line during streaming; returns True once a
    substantial line has appeared too many times (consecutive OR alternating), so the
    caller STOPS consuming the stream (#1: stop the runaway).
  * _dedup_repeated_lines — drops later duplicates of a substantial line from the
    final answer (#2: clean the residue that streamed before the stop).

Citations and bullet markers are ignored for the comparison key, so the same point
with the same chip still counts as a repeat.
"""
from src.features.ai_assistant.routes._helpers import (
    _RepetitionGuard,
    _dedup_repeated_lines,
    _tail_repeats,
    _collapse_repeats,
)

# A real intra-line degeneration loop: a phrase echoed with NO newline (GENERIC over
# 107 sources produced 168k chars of this in a single line, ~11 min stream).
_LOOP_UNIT = "dem Recht der Verkehrssicherheit (BEG, BStrMKnotV), "


# ── _RepetitionGuard ─────────────────────────────────────────────────────────

def test_distinct_lines_no_loop():
    g = _RepetitionGuard(max_repeats=4)
    lines = [
        "Das Modul behandelt audio-visuelle Medien wie Audio, Grafik und Video.",
        "Die drei Hauptkapitel sollten je in einem Monat bearbeitet werden.",
        "Die Formelsammlung dient zur Selbstkontrolle, nicht zur Klausur.",
    ]
    assert not any(g.is_loop(ln) for ln in lines)


def test_same_substantial_line_triggers_on_fourth():
    g = _RepetitionGuard(max_repeats=4)
    line = "Die Modulautoren bitten um Toleranz und konstruktives Feedback."
    assert g.is_loop(line) is False  # 1
    assert g.is_loop(line) is False  # 2
    assert g.is_loop(line) is False  # 3
    assert g.is_loop(line) is True   # 4 -> loop


def test_alternating_lines_trigger():
    # A-B-A-B-A-B: the user's actual failure mode (a few bullets cycling).
    g = _RepetitionGuard(max_repeats=4)
    a = "Die Modulautoren sind für die Inhalte des Moduls verantwortlich."
    b = "Die Modulautoren sind an informativen WWW-Links interessiert."
    seq = [a, b, a, b, a, b, a]
    assert any(g.is_loop(ln) for ln in seq)


def test_same_line_different_chip_still_counts():
    g = _RepetitionGuard(max_repeats=4)
    base = "Die Modulautoren bitten um Toleranz und konstruktives Feedback"
    variants = [f"{base} [1, S. 12]", f"{base} [1, S. 13]", f"{base} [2, 03:12]", f"{base} [1, #154 | Toleranz]"]
    assert [g.is_loop(v) for v in variants][-1] is True


def test_short_lines_never_loop():
    g = _RepetitionGuard(max_repeats=4)
    for _ in range(10):
        assert g.is_loop("- ja") is False
        assert g.is_loop("|---|---|") is False


# ── _dedup_repeated_lines ────────────────────────────────────────────────────

def test_drops_later_duplicate_keeps_first():
    text = (
        "- Die Modulautoren bitten um Toleranz und konstruktives Feedback. [1, S. 12]\n"
        "- Text bleibt das zentrale Medium im Modul. [1, S. 13]\n"
        "- Die Modulautoren bitten um Toleranz und konstruktives Feedback. [1, S. 12]"
    )
    out = _dedup_repeated_lines(text)
    assert out.count("Toleranz und konstruktives Feedback") == 1
    assert "zentrale Medium" in out


def test_duplicate_ignoring_citation_difference():
    text = (
        "- Die Modulautoren sind für die Inhalte verantwortlich. [1, S. 12]\n"
        "- Die Modulautoren sind für die Inhalte verantwortlich. [1, S. 13]"
    )
    assert _dedup_repeated_lines(text).count("für die Inhalte verantwortlich") == 1


def test_keeps_blank_and_short_lines():
    text = "## Überblick\n\n- ok\n\n- ok"
    # Short/heading/blank lines are not deduped away.
    assert _dedup_repeated_lines(text) == text


# ── _tail_repeats (intra-line loop, no newline) ──────────────────────────────

def test_tail_repeats_catches_intra_line_loop():
    buf = "Die Dokumente behandeln Themen wie " + _LOOP_UNIT * 60
    assert _tail_repeats(buf) is True


def test_tail_repeats_ignores_normal_prose():
    prose = ("Die Dokumente umfassen Zivilrecht, Strafrecht, Verwaltungsrecht, "
             "Arbeitsrecht und Sozialrecht, jeweils mit eigenen Verfahrensvorschriften "
             "und Zuständigkeiten der Behörden und Gerichte. ") * 3
    assert _tail_repeats(prose) is False


def test_tail_repeats_needs_enough_repeats():
    # Only 3 repeats (< repeats=5) → not yet a loop.
    assert _tail_repeats("Anfang " + _LOOP_UNIT * 3) is False
    assert _tail_repeats("Anfang " + _LOOP_UNIT * 6) is True


def test_tail_repeats_empty_and_short():
    assert _tail_repeats("") is False
    assert _tail_repeats("kurzer Satz ohne Wiederholung.") is False


# ── _collapse_repeats (clean the residue) ────────────────────────────────────

def test_collapse_repeats_shrinks_loop_residue():
    buf = "Themen wie " + _LOOP_UNIT * 40
    out = _collapse_repeats(buf)
    assert out.count("BStrMKnotV") == 1
    assert len(out) < 200


def test_collapse_repeats_leaves_normal_text():
    text = "- Zivilrecht\n- Strafrecht\n- Verwaltungsrecht"
    assert _collapse_repeats(text) == text
