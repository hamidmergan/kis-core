"""Die Grenzen der Zusammenfassung widersprechen sich nie, sie sind gerechnet."""

import math

from src import limits as l
from src.utils.file_validation import SUMMARY_EXTENSIONS


def test_zehn_dateien_in_voller_groesse_sind_erlaubt():
    assert l.SUMMARY_MAX_TOTAL_CHARS == l.SUMMARY_MAX_SOURCES * l.SUMMARY_MAX_CHARS_PER_SOURCE


def test_das_kontingent_passt_in_die_teilegrenze():
    noetig = math.ceil(l.SUMMARY_MAX_TOTAL_CHARS / l.SUMMARY_PART_MIN_CHARS)
    assert noetig <= l.SUMMARY_MAX_PARTS_PER_JOB


def test_alle_teile_passen_mit_mindestfakten_ins_budget():
    budget = l.AIA_TOOL_CONTEXT_MAX_CHARS - l.SUMMARY_PROMPT_RESERVE_CHARS
    assert l.SUMMARY_MAX_PARTS_PER_JOB * l.SUMMARY_FACTS_MIN_CHARS <= budget


def test_der_rueckfall_der_teilgroesse_liegt_unter_der_gemessenen_wand():
    assert l.SUMMARY_PART_MIN_CHARS <= l.SUMMARY_PART_FALLBACK_CHARS < 139_000


def test_pdf_wird_angenommen():
    assert ".pdf" in SUMMARY_EXTENSIONS
