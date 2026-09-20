"""Die Grenzen der Zusammenfassung widersprechen sich nie, sie sind gerechnet."""

from src import limits as l
from src.features.summary.window import tokens_needed
from src.utils.file_validation import SUMMARY_EXTENSIONS


def test_alle_quellen_passen_mit_mindestfakten_ins_budget():
    budget = l.AIA_TOOL_CONTEXT_MAX_CHARS - l.SUMMARY_PROMPT_RESERVE_CHARS
    assert l.SUMMARY_MAX_SOURCES * l.SUMMARY_FACTS_MIN_CHARS <= budget


def test_die_teilgroessen_sind_weg():
    """Ohne Vorab-Schnitt darf keine Zahl mehr von Teilen reden."""
    assert not hasattr(l, "SUMMARY_MAX_PARTS_PER_JOB")
    assert not hasattr(l, "SUMMARY_PART_MIN_CHARS")
    assert not hasattr(l, "SUMMARY_PART_FALLBACK_CHARS")


def test_die_groesste_datei_braucht_ein_grosses_fenster():
    """Die erlaubte Dateigroesse passt ins gemessene 262k-Fenster, nicht in ein kleines."""
    noetig = tokens_needed(l.SUMMARY_MAX_CHARS_PER_SOURCE, l.SUMMARY_WRITE_MAX_TOKENS)
    assert noetig < 262_144
    assert noetig > 20_080


def test_pdf_wird_angenommen():
    assert ".pdf" in SUMMARY_EXTENSIONS
