# backend/tests/test_citation_dedup.py
"""Per-line chip de-duplication: when two chips on one line point to the SAME source +
position (e.g. the model emits two chunk chips that resolve to the identical spot),
drop the later one. Distinct highlight regions on the same page (different @offset) and
the same position on OTHER lines are kept."""
from src.features.ai_assistant.routes._helpers import _dedup_line_chips, _dedup_chips


def test_drops_identical_adjacent_media_chip():
    line = ("Austausch über Erfahrungen, Tipps und Fragen "
            "[1, 37:24 | Austausch Erfahrungen]. [1, 37:24 | Tipps Fragen]")
    out = _dedup_line_chips(line)
    assert out.count("[1, 37:24") == 1
    # keeps the FIRST chip; trailing duplicate (and its stray space) removed
    assert out == ("Austausch über Erfahrungen, Tipps und Fragen "
                   "[1, 37:24 | Austausch Erfahrungen].")


def test_drops_exact_duplicate_pdf_chip():
    out = _dedup_line_chips("Die Methode nutzt einen Test [2, S. 5 | Test] [2, S. 5 | Test]")
    assert out.count("[2, S. 5") == 1


def test_collapses_three_identical_to_one():
    out = _dedup_line_chips("x [1, 02:59 | a] [1, 02:59 | b] [1, 02:59 | c]")
    assert out.count("[1, 02:59") == 1


def test_keeps_different_offset_regions_same_page():
    # Two different highlight regions on the SAME page are meaningful -> both stay.
    line = "Mehrere Stellen [1, S. 5@10-40 | erste] [1, S. 5@50-80 | zweite]"
    out = _dedup_line_chips(line)
    assert out.count("[1, S. 5@") == 2


def test_keeps_different_source_same_position():
    out = _dedup_line_chips("Beides [1, 37:24 | a] [2, 37:24 | b]")
    assert "[1, 37:24" in out and "[2, 37:24" in out


def test_keeps_different_page_same_source():
    out = _dedup_line_chips("Zwei Seiten [1, S. 5 | a] [1, S. 6 | b]")
    assert "[1, S. 5" in out and "[1, S. 6" in out


def test_dedup_is_per_line_not_global():
    # The same position on TWO different lines -> both kept (each sentence keeps its chip).
    text = "Erster Satz [1, S. 5 | a].\nZweiter Satz [1, S. 5 | b]."
    out = _dedup_chips(text)
    assert out.count("[1, S. 5") == 2


def test_table_row_duplicate_chip_collapsed_separator_agnostic():
    # In a table cell chips use the ❘ separator; an identical position still collapses.
    out = _dedup_line_chips("| Abgabe | 03.07. [4, S. 6 ❘ Abgabe] [4, S. 6 ❘ Abgabe] |")
    assert out.count("[4, S. 6") == 1
