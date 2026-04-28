"""Date/time parser for the schedule pipeline: ISO, DE, EN formats to date/time objects."""

import re
from datetime import date, time
from typing import Optional


_MONTHS = {
    "januar": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dez": 12, "dec": 12,
}


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


def _fmt_hms(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _normalize_date(raw: str) -> Optional[str]:
    """Convert a matched year-FULL date string to ISO 'YYYY-MM-DD'. Returns None on failure."""
    s = raw.strip().replace(" ", " ")
    # ISO
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD.MM.YYYY
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # D. Month YYYY (German)
    m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜüß]+)\s+(\d{4})", s)
    if m:
        d, mo_str, y = m.groups()
        mo = _MONTHS.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    # Month D, YYYY (English)
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m:
        mo_str, d, y = m.groups()
        mo = _MONTHS.get(mo_str.lower())
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"
    return None


def _normalize_partial_date(raw: str) -> Optional[tuple[int, int]]:
    """Year-less date → (month, day). Returns None on failure."""
    s = raw.strip().replace(" ", " ")
    # DD.MM.
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.", s)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        return (mo, d) if 1 <= mo <= 12 and 1 <= d <= 31 else None
    # D. Month (German)
    m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜüß]+)", s)
    if m:
        d = int(m.group(1))
        mo = _MONTHS.get(m.group(2).lower())
        if mo and 1 <= d <= 31:
            return (mo, d)
    # Month D (English)
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})", s)
    if m:
        mo = _MONTHS.get(m.group(1).lower())
        d = int(m.group(2))
        if mo and 1 <= d <= 31:
            return (mo, d)
    return None


def _resolve_current_year(today_d: date, month: int, day: int) -> Optional[date]:
    """Year-less dates ALWAYS resolve to the current year. If the resulting date
    is in the past, it's shown dimmed by the UI — we do NOT hallucinate a future
    year. Returns None on invalid MD."""
    try:
        return date(today_d.year, month, day)
    except ValueError:
        return None
