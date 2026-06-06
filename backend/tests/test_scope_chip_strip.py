"""A single-page scope summary ("fasse Seite 30 zusammen") drops citation chips entirely.

In nav-only mode every line would carry the SAME page chip for the page the user
explicitly named — pure noise with no highlight to differentiate. _strip_resolved_citation_chips
removes the resolved chips and tidies the orphaned spaces/punctuation. Multi-page scope
and media scope keep their (differentiating) chips, so only the stripping primitive is
exercised here; the routing flag (scope_single_page = len(scope_pages) == 1) decides when.
"""
from src.features.ai_assistant.routes._helpers import (
    _strip_resolved_citation_chips,
    _append_scope_anchor,
    _nav_only_chips,
)


def test_strips_single_page_chip_and_fixes_punctuation():
    assert _strip_resolved_citation_chips(
        "Bit pro Sample (K) [1, S. 30] ."
    ) == "Bit pro Sample (K)."


def test_strips_multiple_chips_on_a_line():
    assert _strip_resolved_citation_chips(
        "Zwei Quellen [1, S. 30] und [2, S. 31] hier."
    ) == "Zwei Quellen und hier."


def test_strips_timestamp_chip():
    assert _strip_resolved_citation_chips("Media [1, 10:30] Ende.") == "Media Ende."


def test_leaves_chipless_text_untouched():
    assert _strip_resolved_citation_chips("Kein Chip hier.") == "Kein Chip hier."


def test_appends_single_bottom_anchor_after_stripping():
    # The full single-page flow: strip the per-line chips, then append ONE chip at the
    # bottom as a click-to-page anchor.
    body = _strip_resolved_citation_chips(
        "- Erstens [1, S. 30].\n- Zweitens [1, S. 30]."
    )
    out = _append_scope_anchor(body, 1, 30)
    assert out.count("[1, S. 30]") == 1
    assert out.rstrip().endswith("[1, S. 30]")
    assert "Erstens" in out and "Zweitens" in out


def test_nav_only_keeps_the_page_chip_for_contrast():
    # The multi-page / media path uses _nav_only_chips, which KEEPS the page/timestamp
    # (it navigates). This is the behaviour single-page scope deliberately diverges from.
    assert "[1, S. 30]" in _nav_only_chips("Text [1, S. 30 | keyword @100-140].")
