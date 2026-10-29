"""The summary limits never contradict each other, they are computed."""

from src import limits as l
from src.utils.file_validation import SUMMARY_EXTENSIONS


def test_die_teilgroessen_sind_weg():
    """Without pre-cutting no number may refer to parts anymore."""
    assert not hasattr(l, "SUMMARY_MAX_PARTS_PER_JOB")
    assert not hasattr(l, "SUMMARY_PART_MIN_CHARS")
    assert not hasattr(l, "SUMMARY_PART_FALLBACK_CHARS")


def test_pdf_wird_angenommen():
    assert ".pdf" in SUMMARY_EXTENSIONS
