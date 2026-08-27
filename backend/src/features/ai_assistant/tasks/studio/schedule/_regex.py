"""Regex-based date extraction (DE + EN + ISO) plus 'to-be-arranged' phrases."""

import re


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

# Short form with several years behind slashes, one candidate per year.
_MULTI_YEAR_SHORTHAND = re.compile(
    r"\b(?P<dm>\d{1,2}\.\d{1,2}\.)(?P<years>\d{4}(?:\s*/\s*\d{4})+)\b"
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

# Month with year without a day, four digits at the end keep section numbers out.
_DATE_PATTERNS_MONTH_ONLY = [
    re.compile(r"\b(?P<date>\d{1,2}\.\d{4})\b"),
]

_DATE_PATTERNS_YEARLESS = [
    # DD.MM. (German short, no year), e.g. "03.07." or "3.7."
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.)(?!\d)"),
    # D. Month (German, no year), e.g. "15. Juli"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE}))(?!\s+\d{{4}})\b", re.IGNORECASE),
    # Month D (English, no year), e.g. "July 15"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}})(?!,?\s*\d{{4}})\b", re.IGNORECASE),
]

# Phrases for open appointments, only the fast path, the rest goes via the model.
_TBD_PATTERNS = [
    re.compile(
        r"(?P<phrase>nach\s+(?:individueller\s+)?(?:Vereinbarung|Absprache)"
        r"|Terminabsprache"
        r"|Termin\s+(?:wird|werden)\s+vereinbart"
        r"|zeitlich\s+nach\s+Absprache"
        r"|Datum\s+nach\s+Absprache"
        r"|to\s+be\s+(?:announced|decided|confirmed))",
        re.IGNORECASE,
    ),
]


# Column boundary in a text line, a pure layout rule without language.
_COLUMN_GAP = re.compile(r"[|\t]|   ")


def _date_in_neighbouring_column(text: str, start: int, end: int) -> bool:
    """If the same line holds a date in another column, the appointment is not open."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    phrase_start, phrase_end = start - line_start, end - line_start
    for date_start, date_end, _raw, _has_year, _prec in _date_candidates_in_text(line):
        if date_start >= phrase_end:
            gap = line[phrase_end:date_start]
        elif date_end <= phrase_start:
            gap = line[date_end:phrase_start]
        else:
            continue
        if _COLUMN_GAP.search(gap):
            return True
    return False


# Two dates close together are usually a span, the model has to confirm it.
_RANGE_MAX_GAP = 15

# A comma or slash between two dates means a list, not a span.
_LIST_SEPARATORS = frozenset(",;/&+")


def _looks_like_range(text: str, end_of_first: int, start_of_second: int) -> bool:
    """Does the text between two dates join them into a span?"""
    if not 0 < start_of_second - end_of_first <= _RANGE_MAX_GAP * 4:
        return False
    gap = text[end_of_first:start_of_second]
    if "\n" in gap or "|" in gap or "\t" in gap:
        return False
    if any(ch.isdigit() for ch in gap):
        return False
    kern = " ".join(gap.split())
    if not kern or len(kern) > _RANGE_MAX_GAP:
        return False
    if all(ch in _LIST_SEPARATORS for ch in kern):
        return False
    return True


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
    # Deduplicate: a year beats no year, a longer hit beats a shorter one.
    found.sort(key=lambda t: (t[0], not t[3], -(t[1] - t[0])))
    result: list[tuple[int, int, str, bool, str]] = []
    last_end = -1
    for s, e, d, hy, prec in found:
        if s >= last_end:
            result.append((s, e, d, hy, prec))
            last_end = e
    return result
