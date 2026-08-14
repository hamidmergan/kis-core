"""WebVTT-Untertitel: Segmente in VTT schreiben und aus VTT zurueckelesen."""

from __future__ import annotations



def _fmt_vtt_time(seconds: float) -> str:
    """Format seconds as WebVTT timestamp ``HH:MM:SS.mmm``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segments_to_vtt(segments: list[dict]) -> str:
    """Convert segments to WebVTT format string."""
    lines: list[str] = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_vtt_time(seg['start'])} --> {_fmt_vtt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _parse_vtt_time(s: str) -> float:
    """Parse a WebVTT/SRT timestamp (``HH:MM:SS.mmm`` or ``MM:SS.mmm``) into seconds."""
    parts = s.replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + float(sec)
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + float(sec)
    return float(s)


def vtt_to_segments(raw: str) -> list[dict]:
    """Parse a WebVTT string back into ``{start, end, text}`` segments."""
    segments: list[dict] = []
    lines = raw.replace("\r", "").split("\n")
    i = 0
    while i < len(lines):
        arrow = lines[i].find("-->")
        if arrow == -1:
            i += 1
            continue
        try:
            start = _parse_vtt_time(lines[i][:arrow].strip())
            end = _parse_vtt_time(lines[i][arrow + 3:].strip().split(" ")[0])
        except (ValueError, IndexError):
            i += 1
            continue
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            text_lines.append(lines[i])
            i += 1
        if text_lines:
            segments.append({"start": start, "end": end, "text": " ".join(text_lines).strip()})
        i += 1
    return segments


