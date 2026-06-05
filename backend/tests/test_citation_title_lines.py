"""A bold-only title line ('**Kurskonzept und organisatorischer Rahmen**') is a
heading, not a claim — it must never carry a citation chip. Markdown headings (#)
are already excluded by is_citable_line; bold titles were not, so the filler
appended a chip right after the title (and a model-emitted one slipped through too).

Two guards:
  * is_citable_line → False for a bold-only title (no fill).
  * _strip_title_line_chips → removes an already-present chip (model-emitted or
    filled) when the line is just a bold title.
"""
from src.features.ai_assistant.routes._helpers import (
    is_citable_line,
    _strip_title_line_chips,
)


# ── is_citable_line: bold titles are not citable ─────────────────────────────

def test_bold_only_title_not_citable():
    assert not is_citable_line("**Kurskonzept und organisatorischer Rahmen**", in_summary=False)


def test_bold_title_with_trailing_colon_not_citable():
    assert not is_citable_line("**Organisatorischer Rahmen:**", in_summary=False)


def test_bold_lead_in_then_text_stays_citable():
    # A bold lead-in followed by real prose is a claim, not a heading.
    assert is_citable_line("**Wichtig:** der Kurs beginnt am 25.03.2026.", in_summary=False)


def test_bold_list_item_stays_citable():
    # A definition-style bullet ("- **Begriff**: ...") is a claim.
    assert is_citable_line("- **Peer-Review**: gegenseitige Begutachtung.", in_summary=False)


# ── _strip_title_line_chips: drop a chip sitting on a bold title ──────────────

def test_strips_chip_from_bold_title():
    line = "**Kurskonzept und organisatorischer Rahmen** [1, S. 5 | Kurskonzept]"
    assert _strip_title_line_chips(line) == "**Kurskonzept und organisatorischer Rahmen**"


def test_strips_offset_chip_from_bold_title():
    line = "**Organisatorischer Rahmen** [1, S. 5 @120-460]"
    assert _strip_title_line_chips(line) == "**Organisatorischer Rahmen**"


def test_keeps_chip_on_normal_sentence():
    line = "Der Kurs beginnt am 25.03.2026 [1, S. 5 | 25.03.2026]."
    assert _strip_title_line_chips(line) == line


def test_keeps_chip_when_bold_lead_in_has_body():
    line = "**Wichtig:** der Kurs beginnt am 25.03.2026 [1, S. 5 | Kurs]."
    assert _strip_title_line_chips(line) == line


def test_untouched_line_without_chip():
    assert _strip_title_line_chips("**Nur ein Titel**") == "**Nur ein Titel**"
