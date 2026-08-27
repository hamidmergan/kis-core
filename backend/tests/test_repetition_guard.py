"""Guard against repetition loops: abort and clean up the remains."""
from src.features.ai_assistant.routes._helpers import (
    _RepetitionGuard,
    _dedup_repeated_lines,
    _tail_repeats,
    _collapse_repeats,
    _strip_source_list,
    _strip_tiny_tables,
)

# A real loop without a line break, from an actual run.
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


# ── _strip_source_list (model-written "Quellen:" enumeration) ─────────────────

def test_strip_source_list_removes_quellen_enumeration():
    text = (
        "Die Hausarbeit muss am 03.07.2026 abgegeben werden.\n\n"
        "Quellen:\n\n"
        "- VL1_25-03-2026.webm | 08:58\n"
        "- 01_Einführung.pdf | S. 6\n"
        "- 02_Publizieren.pdf | S. 4\n"
    )
    names = ["VL1_25-03-2026.webm", "01_Einführung.pdf", "02_Publizieren.pdf"]
    out = _strip_source_list(text, names)
    assert "Quellen:" not in out
    assert "VL1_25-03-2026.webm" not in out and "01_Einführung.pdf" not in out
    assert "Die Hausarbeit muss am 03.07.2026 abgegeben werden." in out


def test_strip_source_list_keeps_inline_filename_mention():
    text = "Laut 01_Einführung.pdf wird das Thema dort ausführlich erklärt und vertieft."
    assert _strip_source_list(text, ["01_Einführung.pdf"]) == text


def test_strip_source_list_noop_without_filenames():
    text = "Quellen:\n- a | S. 1\n- b | S. 2"
    assert _strip_source_list(text, []) == text


# ── _strip_tiny_tables (one-row table duplicating a sentence) ─────────────────

def test_strip_tiny_tables_drops_one_row_table_keeps_prose():
    text = (
        "Die Hausarbeit muss am **03.07.2026** abgegeben werden.\n\n"
        "| Datum | Termin | Uhrzeit |\n"
        "|---|---|---|\n"
        "| 03.07.2026 | Abgabe Hausarbeit | — |\n"
    )
    out = _strip_tiny_tables(text)
    assert "| Datum |" not in out
    assert "Die Hausarbeit muss am **03.07.2026** abgegeben werden." in out


def test_strip_tiny_tables_keeps_multirow_table():
    text = (
        "Termine:\n\n"
        "| Datum | Termin |\n"
        "|---|---|\n"
        "| 01.04. | Start |\n"
        "| 03.07. | Abgabe |\n"
    )
    out = _strip_tiny_tables(text)
    assert "| 01.04. | Start |" in out and "| 03.07. | Abgabe |" in out


def test_strip_tiny_tables_keeps_table_when_sole_content():
    text = "| Datum | Termin |\n|---|---|\n| 03.07. | Abgabe |"
    assert "| 03.07. | Abgabe |" in _strip_tiny_tables(text)
