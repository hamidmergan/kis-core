"""Die Grenzen der Zusammenfassung widersprechen sich nie, sie sind gerechnet."""

from src import limits as l
from src.utils.file_validation import SUMMARY_EXTENSIONS


def test_die_teilgroessen_sind_weg():
    """Ohne Vorab-Schnitt darf keine Zahl mehr von Teilen reden."""
    assert not hasattr(l, "SUMMARY_MAX_PARTS_PER_JOB")
    assert not hasattr(l, "SUMMARY_PART_MIN_CHARS")
    assert not hasattr(l, "SUMMARY_PART_FALLBACK_CHARS")


def test_pdf_wird_angenommen():
    assert ".pdf" in SUMMARY_EXTENSIONS
