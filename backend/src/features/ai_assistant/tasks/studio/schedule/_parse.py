"""Date/time parser for the schedule pipeline: ISO, DE, EN formats to date/time objects."""

import re
from datetime import date, time
from typing import Optional


# Days written out in words, so a spoken date is found without the model.
_ORDINALS_DE = {
    "erste": 1, "zweite": 2, "dritte": 3, "vierte": 4, "fünfte": 5, "fuenfte": 5,
    "sechste": 6, "siebte": 7, "siebente": 7, "achte": 8, "neunte": 9, "zehnte": 10,
    "elfte": 11, "zwölfte": 12, "zwoelfte": 12, "dreizehnte": 13, "vierzehnte": 14,
    "fünfzehnte": 15, "fuenfzehnte": 15, "sechzehnte": 16, "siebzehnte": 17,
    "achtzehnte": 18, "neunzehnte": 19, "zwanzigste": 20,
    "dreißigste": 30, "dreissigste": 30,
}
_ORDINALS_EN = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
    "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirtieth": 30,
}
ORDINAL_DAYS: dict[str, int] = {**_ORDINALS_DE, **_ORDINALS_EN}
# The twenties and 31 are built from the ones in front of the tens.
for _tens_word, _tens in (("zwanzigste", 20), ("dreißigste", 30), ("dreissigste", 30)):
    for _ones_word, _ones in (("einund", 1), ("zweiund", 2), ("dreiund", 3), ("vierund", 4),
                              ("fünfund", 5), ("fuenfund", 5), ("sechsund", 6),
                              ("siebenund", 7), ("achtund", 8), ("neunund", 9)):
        if _tens + _ones <= 31:
            ORDINAL_DAYS[_ones_word + _tens_word] = _tens + _ones
for _tens_word, _tens in (("twenty-", 20), ("thirty-", 30)):
    for _ones_word, _ones in tuple(_ORDINALS_EN.items())[:9]:
        if _tens + _ones <= 31:
            ORDINAL_DAYS[_tens_word + _ones_word] = _tens + _ones


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parse_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, TypeError, IndexError):
        return None


def _range_end_date(cand: dict, due_date_obj: Optional[date],
                    today_d: date) -> Optional[date]:
    """The end date of a confirmed span, or None."""
    ende = None
    if cand.get("date_end_iso"):
        ende = _parse_date(cand["date_end_iso"])
    elif cand.get("date_end_partial"):
        mo, da = cand["date_end_partial"]
        if due_date_obj:
            # A year-less end is the first such day on or after the start.
            ende = next((d for d in (_in_year(due_date_obj.year + k, mo, da) for k in (0, 1, 2))
                         if d and d >= due_date_obj), None)
        else:
            ende, _ = _resolve_year(today_d, mo, da)
    if ende and due_date_obj and ende <= due_date_obj:
        return None
    return ende


def _in_year(year: int, month: int, day: int) -> Optional[date]:
    """The day in that year, None when it does not exist there (29 February)."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _year_written(year: int, text: str) -> bool:
    """Does the text write this year, in full or as the short year of a numeric date?"""
    if re.search(rf"(?<!\d){year}(?!\d)", text):
        return True
    return bool(re.search(rf"\d{{1,2}}[./-]\d{{1,2}}[./-]{year % 100:02d}(?!\d)", text))


def _year_evidence(candidates: list[dict], entries: list[dict]) -> dict[tuple[int, int], set[int]]:
    """Per month and day, the years a source writes out for it."""
    belegt: dict[tuple[int, int], set[int]] = {}
    for c in candidates:
        d = _parse_date(c.get("date_iso"))
        if d and (c.get("date_precision") or "day") == "day":
            belegt.setdefault((d.month, d.day), set()).add(d.year)
    for e in entries:
        d = e.get("due_date")
        if not d or (e.get("date_precision") or "day") != "day" or e.get("year_assumed"):
            continue
        # Older model entries carry years their quote never wrote, only a written one counts.
        if e.get("origin") == "llm" and not any(
                _year_written(d.year, str(r.get("raw_quote") or ""))
                for r in e.get("source_refs") or []):
            continue
        belegt.setdefault((d.month, d.day), set()).add(d.year)
    return belegt


# Summer semester runs from March, winter semester from September.
_SEMESTER_START_MONTHS = (3, 9)


def _semester_start(today_d: date) -> date:
    """First day of the semester today falls in."""
    month = max((m for m in _SEMESTER_START_MONTHS if m <= today_d.month), default=None)
    if month is None:
        return date(today_d.year - 1, _SEMESTER_START_MONTHS[-1], 1)
    return date(today_d.year, month, 1)


def _resolve_year(today_d: date, month: int, day: int,
                  evidence: Optional[dict] = None) -> tuple[Optional[date], bool]:
    """A year-less date and whether its year is only assumed, a written year wins over the semester."""
    years = (evidence or {}).get((month, day))
    if years:
        dates = [d for d in (_in_year(y, month, day) for y in years) if d]
        if not dates:
            return None, False
        # The nearest written occurrence, on a tie the coming one.
        return min(dates, key=lambda d: (abs((d - today_d).days), d < today_d)), False
    # The first occurrence from the start of the running semester on.
    start = _semester_start(today_d)
    for y in (start.year, start.year + 1):
        d = _in_year(y, month, day)
        if d and d >= start:
            return d, True
    return None, False


def _candidate_start(cand: dict, today_d: date, evidence: Optional[dict] = None,
                     use_end: bool = False) -> tuple[Optional[date], bool]:
    """The date of a candidate and whether its year is only assumed."""
    if cand.get("is_tbd"):
        return None, False
    if cand.get("date_iso"):
        return _parse_date(cand["date_iso"]), False
    if not cand.get("partial_date"):
        return None, False
    mo, da = cand["partial_date"]
    ende = _parse_date(cand.get("date_end_iso")) if use_end else None
    if ende:
        # A written end fixes the year, the start is the last such day before it.
        start = next((d for d in (_in_year(ende.year - k, mo, da) for k in (0, 1, 2))
                      if d and d <= ende), None)
        if start:
            return start, False
    return _resolve_year(today_d, mo, da, evidence)
