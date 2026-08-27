"""Checks the title match that pulls a named source forward."""
from src.features.ai_assistant.routes.chat import _named_source_ids, _title_word_match


# Realistic page-1 title headers (gesetze-im-internet.de format), lowercased + trimmed.
HEADERS = {
    186: "ein service des ... www.gesetze-im-internet.de grundgesetz für die bundesrepublik deutschland gg ausfertigungsdatum",
    9:   "ein service ... kündigungsschutzgesetz kschg ausfertigungsdatum",
    13:  "ein service ... allgemeines gleichbehandlungsgesetz agg ausfertigungsdatum",
    82:  "ein service ... telekommunikationsgesetz tkg ... die zuständigen stellen ...",
    63:  "ein service ... markengesetz markeng ausfertigungsdatum",
    # fragment: copy starts mid-statute, no self-name in the header
    102: "dem beteiligten steht gleich, wer durch die tätigkeit oder die entscheidung einen vorteil",
}


def test_inflected_full_name_matches_unique_source():
    # "Grundgesetzes" (genitive) -> header word "grundgesetz" (token extends base by 2)
    assert _named_source_ids("Was schützt Artikel 1 des Grundgesetzes?", HEADERS) == {186}


def test_substantial_stem_plus_lawtype_suffix_matches():
    # The header adds a real law-type word to the typed stem
    assert _named_source_ids("Greift hier der besondere Kündigungsschutz?", HEADERS) == {9}


def test_generic_inflection_is_rejected():
    # "allgemeine"->"allgemeines" (+1) must NOT pull in AGG; only the real name (KSchG) wins.
    assert _named_source_ids("Nach welcher Wartezeit greift der allgemeine Kündigungsschutz?", HEADERS) == {9}
    # "stelle"->"stellen" (+1) must NOT pull in TKG.
    assert _named_source_ids("Welche Stelle ist hier zuständig?", HEADERS) == set()


def test_short_common_stem_does_not_match_law_compound():
    # A short everyday word must not pull a statute forward.
    assert _named_source_ids("Aus welchem Grund ist das hier geregelt?", HEADERS) == set()


def test_generic_word_hitting_many_headers_is_ignored():
    # "gesetz" appears in several headers -> non-discriminative -> no boost (never floods).
    assert _named_source_ids("Welches Gesetz regelt das?", HEADERS) == set()


def test_fragment_without_self_name_is_not_matched():
    # AO copy is a fragment; "Abgabenordnung" is not in its header -> no invented boost.
    assert _named_source_ids("Was regelt die Abgabenordnung?", HEADERS) == set()


def test_two_named_laws_both_returned():
    assert _named_source_ids("Unterschied zwischen Grundgesetz und Markengesetz?", HEADERS) == {186, 63}


def test_empty_inputs():
    assert _named_source_ids("", HEADERS) == set()
    assert _named_source_ids("Grundgesetz", {}) == set()


def test_title_word_match_rules():
    assert _title_word_match("grundgesetz", "grundgesetz")             # exact
    assert _title_word_match("markengesetz", "markengesetz")           # exact
    assert _title_word_match("kündigungsschutz", "kündigungsschutzgesetz")  # ≥7 stem + suffix
    assert _title_word_match("grundgesetzes", "grundgesetz")           # inflection (≤3)
    assert not _title_word_match("marke", "markengesetz")              # stem <7 → too loose
    assert not _title_word_match("grund", "grundgesetz")               # stem <7 → too loose
    assert not _title_word_match("allgemeine", "allgemeines")          # +1 inflection on header side
    assert not _title_word_match("stelle", "stellen")                 # +1 inflection on header side
