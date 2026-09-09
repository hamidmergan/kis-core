"""Turns a pasted transcript into Whisper-like segments, the known formats and no guessing beyond that."""
from __future__ import annotations

import re

from src.limits import YOUTUBE_LAST_SEGMENT_SECONDS, YOUTUBE_TRANSCRIPT_MAX_CHARS
from src.services.subtitle_converter import vtt_to_segments
from src.services.web_page_fetch import LinkError

_STAMP = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})"
_STAMP_ALONE = re.compile(rf"^\s*{_STAMP}\s*$")
_STAMP_INLINE = re.compile(rf"^\s*{_STAMP}\s+(\S.*)$")
_TIMING_LINE = re.compile(r"^[ \t]*(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3}[ \t]*-->", re.MULTILINE)

# The words YouTube's hidden time label uses, by interface language, longest first.
_UNIT_WORDS = (
    "stunden", "stunde", "minuten", "minute", "sekunden", "sekunde",
    "hours", "hour", "minutes", "seconds", "second",
    "heures", "heure", "secondes", "seconde",
    "horas", "hora", "minutos", "minuto", "segundos", "segundo",
    "ore", "ora", "minuti", "secondi", "secondo",
    "uur", "minuut", "seconden",
    "saat", "dakika", "saniye",
    "godziny", "godzina", "godzin", "minuty", "minuta", "minut", "sekundy", "sekunda", "sekund",
)
_UNITS = "|".join(sorted(set(_UNIT_WORDS), key=len, reverse=True))
# "6 Sekunden" or "1 Minute, 6 Sekunden", glued to the text with no separator at all.
_LABEL = rf"(?:\d{{1,3}}[ \t]*(?:{_UNITS})(?:,[ \t]*)?)+"
_STAMP_GLUED = re.compile(rf"^\s*{_STAMP}{_LABEL}(.*)$", re.IGNORECASE)
# A label in a language the list does not know stays in the text, the stamp still counts.
_STAMP_DIGIT = re.compile(rf"^\s*{_STAMP}(?=\d)(.*)$")


def parse_transcript(text: str) -> list[dict]:
    """Segments with start, end and text, or a LinkError naming what is wrong."""
    text = (text or "").replace("\r", "")
    if len(text) > YOUTUBE_TRANSCRIPT_MAX_CHARS:
        raise LinkError("ai.youtube.tooLong", 400)
    if not text.strip():
        raise LinkError("ai.youtube.emptyTranscript", 400)
    # A timing line with an arrow means SRT or VTT, the shared parser knows both.
    segments = vtt_to_segments(text) if _TIMING_LINE.search(text) else _parse_player_copy(text)
    segments = [s for s in segments if s["text"].strip()]
    if not segments:
        raise LinkError("ai.youtube.emptyTranscript", 400)
    return segments


def _seconds(match: re.Match) -> float:
    hours, minutes, seconds = match.group(1), match.group(2), match.group(3)
    return float(int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds))


def _stamped_line(line: str) -> tuple[float, list[str]] | None:
    """The stamp and the text of one line, None when the line carries no stamp."""
    if m := _STAMP_ALONE.match(line):
        return _seconds(m), []
    for pattern in (_STAMP_INLINE, _STAMP_GLUED, _STAMP_DIGIT):
        if m := pattern.match(line):
            return _seconds(m), [m.group(4).strip()]
    return None


def _parse_player_copy(text: str) -> list[dict]:
    """The text copied from the YouTube player, in the forms browsers produce."""
    starts: list[tuple[float, list[str]]] = []
    for line in text.split("\n"):
        if stamped := _stamped_line(line):
            starts.append(stamped)
        elif starts and line.strip():
            starts[-1][1].append(line.strip())
    if not starts:
        raise LinkError("ai.youtube.noTimestamps", 400)
    segments: list[dict] = []
    for i, (start, lines) in enumerate(starts):
        following = starts[i + 1][0] if i + 1 < len(starts) else start + YOUTUBE_LAST_SEGMENT_SECONDS
        # Stamps out of order never make a segment run backwards.
        end = following if following > start else start + 0.5
        segments.append({"start": start, "end": end, "text": " ".join(lines)})
    return segments
