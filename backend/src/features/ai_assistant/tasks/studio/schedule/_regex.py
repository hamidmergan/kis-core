"""Regex-based date spotting (DE + EN + ISO), it decides which chunks reach the model."""

import re

from src.features.ai_assistant.tasks.studio.schedule._parse import ORDINAL_DAYS


# Patterns for German, ISO and mixed date forms.
_MONTH_DE = (
    "januar|februar|märz|maerz|april|mai|juni|juli|august|"
    "september|oktober|november|dezember|jan|feb|mär|mar|apr|"
    "jun|jul|aug|sep|sept|okt|nov|dez"
)
_MONTH_EN = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december|jan|feb|mar|apr|"
    "jun|jul|aug|sep|sept|oct|nov|dec"
)

_DATE_PATTERNS_WITH_YEAR = [
    # DD.MM.YYYY
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\b"),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b"),
    # D. Month YYYY (German), e.g. "15. Juli 2026"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\s+\d{{4}})\b", re.IGNORECASE),
    # With a period before the year too, otherwise the year is lost.
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\.\s*\d{{4}})\b", re.IGNORECASE),
    # Month D, YYYY (English), e.g. "July 15, 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
]

# Written-out days, longest first so "einundzwanzigste" wins over "zwanzigste".
_ORDINAL_WORDS = "|".join(
    sorted((re.escape(w) for w in ORDINAL_DAYS), key=len, reverse=True))
_MONTH_ANY = f"{_MONTH_DE}|{_MONTH_EN}"

_DATE_PATTERNS_WITH_YEAR.append(
    # "dritten Februar 2026" / "the third of February 2026"
    re.compile(rf"\b(?P<date>(?:the\s+)?(?:{_ORDINAL_WORDS})[nmrs]?\s+(?:of\s+)?"
               rf"(?:{_MONTH_ANY})\s*,?\s*\d{{4}})\b", re.IGNORECASE)
)

_DATE_PATTERNS_WITH_YEAR += [
    # DD.MM.YY, the century is added when the date is normalized.
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.\d{2})\b(?!\.\d)"),
    # DD/MM/YYYY and DD-MM-YYYY, day first as in German usage.
    re.compile(r"\b(?P<date>\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(?P<date>\d{1,2}-\d{1,2}-\d{4})\b"),
    # "3 July 2026", "3rd of July 2026", also a German month without the period.
    re.compile(rf"\b(?P<date>\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH_ANY})\s+\d{{4}})\b",
               re.IGNORECASE),
]

# Month with year without a day, four digits at the end keep section numbers out.
_DATE_PATTERNS_MONTH_ONLY = [
    re.compile(r"\b(?P<date>\d{1,2}\.\d{4})\b"),
    # "Januar 2026", "July 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_ANY})\s+\d{{4}})\b", re.IGNORECASE),
]

# A bare month word only counts after a word that makes it a time statement.
_MONTH_PREP = (r"(?:im|ab|bis|seit|in|by|until|from|since|during"
               r"|anfang|mitte|ende|early|mid|late|end\s+of|beginning\s+of|middle\s+of)")
_DATE_PATTERNS_MONTH_YEARLESS = [
    re.compile(rf"\b{_MONTH_PREP}\s+(?P<date>(?:{_MONTH_ANY}))\b(?!\s*,?\s*\d)", re.IGNORECASE),
]

_DATE_PATTERNS_YEARLESS = [
    # DD.MM. (German short, no year), e.g. "03.07." or "3.7."
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.)(?!\d)"),
    # D. Month (German, no year), e.g. "15. Juli"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE}))(?!\s+\d{{4}})\b", re.IGNORECASE),
    # Month D (English, no year), e.g. "July 15"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}})(?!,?\s*\d{{4}})\b", re.IGNORECASE),
]

_DATE_PATTERNS_YEARLESS.append(
    # "3 July", "3rd of July", no year behind it
    re.compile(rf"\b(?P<date>\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH_ANY}))(?!\s*,?\s*\d{{4}})\b",
               re.IGNORECASE)
)

_DATE_PATTERNS_YEARLESS.append(
    # "dritten Februar" / "the third of February"
    re.compile(rf"\b(?P<date>(?:the\s+)?(?:{_ORDINAL_WORDS})[nmrs]?\s+(?:of\s+)?"
               rf"(?:{_MONTH_ANY}))(?!\s*,?\s*\d{{4}})\b", re.IGNORECASE)
)


def _date_candidates_in_text(text: str) -> list[tuple[int, int, str, bool, str]]:
    """Finds the date spots with their year flag and precision."""
    found: list[tuple[int, int, str, bool, str]] = []
    for pat in _DATE_PATTERNS_WITH_YEAR:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True, "day"))
    for pat in _DATE_PATTERNS_MONTH_ONLY:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True, "month"))
    for pat in _DATE_PATTERNS_YEARLESS:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), False, "day"))
    for pat in _DATE_PATTERNS_MONTH_YEARLESS:
        for m in pat.finditer(text):
            found.append((m.start("date"), m.end("date"), m.group("date"), False, "month"))
    # Deduplicate: a year beats no year, a longer hit beats a shorter one.
    found.sort(key=lambda t: (t[0], not t[3], -(t[1] - t[0])))
    result: list[tuple[int, int, str, bool, str]] = []
    last_end = -1
    for s, e, d, hy, prec in found:
        if s >= last_end:
            result.append((s, e, d, hy, prec))
            last_end = e
    return result
