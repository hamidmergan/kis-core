"""Convert ElevenLabs character-level alignment data to SRT / VTT / TXT subtitles."""

from __future__ import annotations

import json


def alignment_to_words(alignment: dict) -> list[dict]:
    """Group character-level alignment into word-level entries.

    Args:
        alignment: Dict with 'characters', 'character_start_times_seconds',
                   'character_end_times_seconds' lists (from ElevenLabs).

    Returns:
        List of ``{"word": str, "start": float, "end": float}`` dicts.
    """
    chars: list[str] = alignment.get("characters", [])
    starts: list[float] = alignment.get("character_start_times_seconds", [])
    ends: list[float] = alignment.get("character_end_times_seconds", [])

    if not chars:
        return []

    words: list[dict] = []
    buf: list[str] = []
    word_start: float | None = None

    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append({"word": "".join(buf), "start": word_start, "end": e})
                buf = []
                word_start = None
            continue
        if word_start is None:
            word_start = s
        buf.append(ch)

    # flush last word
    if buf and word_start is not None:
        words.append({"word": "".join(buf), "start": word_start, "end": ends[-1] if ends else word_start})

    return words


def words_to_segments(
    words: list[dict],
    max_words: int = 8,
    max_dur: float = 5.0,
) -> list[dict]:
    """Group words into subtitle cues (segments).

    Flushes a segment when:
    - sentence-end punctuation is encountered (. ! ?)
    - word count reaches *max_words*
    - segment duration exceeds *max_dur* seconds

    Returns:
        List of ``{"text": str, "start": float, "end": float}`` dicts.
    """
    if not words:
        return []

    segments: list[dict] = []
    buf: list[str] = []
    seg_start: float | None = None
    seg_end: float = 0.0

    for w in words:
        if seg_start is None:
            seg_start = w["start"]
        buf.append(w["word"])
        seg_end = w["end"]

        sentence_end = w["word"].rstrip().endswith((".", "!", "?"))
        over_words = len(buf) >= max_words
        over_dur = (seg_end - seg_start) >= max_dur

        if sentence_end or over_words or over_dur:
            segments.append({"text": " ".join(buf), "start": seg_start, "end": seg_end})
            buf = []
            seg_start = None

    # flush remainder
    if buf and seg_start is not None:
        segments.append({"text": " ".join(buf), "start": seg_start, "end": seg_end})

    return segments


def _fmt_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp ``HH:MM:SS,mmm``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_vtt_time(seconds: float) -> str:
    """Format seconds as WebVTT timestamp ``HH:MM:SS.mmm``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    """Convert segments to SRT format string."""
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(seg['start'])} --> {_fmt_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def segments_to_vtt(segments: list[dict]) -> str:
    """Convert segments to WebVTT format string."""
    lines: list[str] = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_vtt_time(seg['start'])} --> {_fmt_vtt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def segments_to_txt(segments: list[dict]) -> str:
    """Convert segments to plain-text transcript."""
    return " ".join(seg["text"] for seg in segments)


def build_subtitles(
    per_slide_data: list[dict],
    slide_pause: float,
) -> dict:
    """Build global subtitle files from per-slide alignment data.

    Args:
        per_slide_data: List of dicts, each with:
            - ``alignment``: ElevenLabs alignment dict (or None for empty slides)
            - ``audio_duration``: duration of that slide's audio in seconds
        slide_pause: pause between slides in seconds

    Returns:
        Dict with ``srt``, ``vtt``, ``txt``, ``alignment_json`` string values.
    """
    all_segments: list[dict] = []
    global_offset = 0.0

    for slide in per_slide_data:
        alignment = slide.get("alignment")
        duration = slide.get("audio_duration", 0.0)

        if alignment:
            words = alignment_to_words(alignment)
            segments = words_to_segments(words)
            for seg in segments:
                all_segments.append({
                    "text": seg["text"],
                    "start": seg["start"] + global_offset,
                    "end": seg["end"] + global_offset,
                })

        global_offset += duration + slide_pause

    return {
        "srt": segments_to_srt(all_segments),
        "vtt": segments_to_vtt(all_segments),
        "txt": segments_to_txt(all_segments),
        "alignment_json": json.dumps(all_segments, ensure_ascii=False),
    }
