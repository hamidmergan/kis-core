"""Nav-only chips for multi-page/-chunk scoped summaries.

A summary of several pages is a SYNTHESIS with no single source location, so
highlighting specific spans lights up many blocks across pages ("wild"). For those
answers we strip each chip down to its page/timestamp only ([1, S. 12]) — the
frontend then just scrolls to the page on click, no yellow highlight. Single-page
scope and normal Q&A keep their precise highlight (untouched).
"""
from src.features.ai_assistant.routes._helpers import _nav_only_chips


def test_strips_offset_and_keyword_from_page_chip():
    text = "Fakt [1, S. 12 @100-200 | Schneeballprinzip]."
    assert _nav_only_chips(text) == "Fakt [1, S. 12]."


def test_strips_keyword_from_two_page_chips():
    text = "Synthese [1, S. 12 | Schneeball] [1, S. 13 | Google Scholar]."
    assert _nav_only_chips(text) == "Synthese [1, S. 12] [1, S. 13]."


def test_strips_keyword_from_timestamp_chip():
    text = "Clip [2, 05:32 | Einleitung]."
    assert _nav_only_chips(text) == "Clip [2, 05:32]."


def test_keeps_chip_without_qnum():
    assert _nav_only_chips("Siehe [S. 5 | Begriff].") == "Siehe [S. 5]."


def test_already_bare_chip_unchanged():
    assert _nav_only_chips("Schon nackt [1, S. 5].") == "Schon nackt [1, S. 5]."


def test_non_chip_text_unchanged():
    assert _nav_only_chips("Kein Chip hier, nur Text.") == "Kein Chip hier, nur Text."
