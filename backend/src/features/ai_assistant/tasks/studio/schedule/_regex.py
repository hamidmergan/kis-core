"""Regex-based date extraction (DE + EN + ISO) plus 'to-be-arranged' phrases."""

import re


# German + ISO + mixed patterns. Captures anchored date strings so the LLM
# only has to classify, not find.
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
    # Month D, YYYY (English), e.g. "July 15, 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
]

_DATE_PATTERNS_YEARLESS = [
    # DD.MM. (German short, no year), e.g. "03.07." or "3.7."
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.)(?!\d)"),
    # D. Month (German, no year), e.g. "15. Juli"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE}))(?!\s+\d{{4}})\b", re.IGNORECASE),
    # Month D (English, no year), e.g. "July 15"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}})(?!,?\s*\d{{4}})\b", re.IGNORECASE),
]

# "Date not yet fixed" patterns: the event is real but happens at a time still
# to be negotiated. We surface these so the schedule shows them as a separate
# 'to be arranged' block in the UI.
_TBD_PATTERNS = [
    re.compile(
        r"(?P<phrase>nach\s+(?:individueller\s+)?(?:Vereinbarung|Absprache)"
        r"|Terminabsprache"
        r"|Termin\s+(?:wird|werden)\s+vereinbart"
        r"|zeitlich\s+nach\s+Absprache"
        r"|Datum\s+nach\s+Absprache"
        r"|to\s+be\s+(?:announced|decided|confirmed)"
        r"|TBA|TBD|TBC)",
        re.IGNORECASE,
    ),
]


def _date_candidates_in_text(text: str) -> list[tuple[int, int, str, bool]]:
    """Return list of (start_index, end_index, matched_string, has_year).
    Year-full matches win over year-less at overlapping positions.
    """
    found: list[tuple[int, int, str, bool]] = []
    for pat in _DATE_PATTERNS_WITH_YEAR:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True))
    for pat in _DATE_PATTERNS_YEARLESS:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), False))
    # Deduplicate: prefer has_year=True, then longer span, then earliest start
    found.sort(key=lambda t: (t[0], not t[3], -(t[1] - t[0])))
    result: list[tuple[int, int, str, bool]] = []
    last_end = -1
    for s, e, d, hy in found:
        if s >= last_end:
            result.append((s, e, d, hy))
            last_end = e
    return result
