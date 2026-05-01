"""SRT/VTT Timestamp-Formatierung + Chunk-Merge mit Offset-Shift.

Wenn Whisper-Transkripte aus mehreren Chunks wieder zusammengeführt werden,
müssen alle Timestamps um den Offset des jeweiligen Chunks verschoben werden."""

import re


# ── Timestamp-Formatierung ────────────────────────────────────────────────────

def seconds_to_srt_timestamp(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")


def seconds_to_vtt_timestamp(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def verbose_json_to_output(data: dict, response_format: str) -> str:
    """Whisper verbose_json → SRT/VTT/Plaintext."""
    if response_format == "srt":
        parts = []
        for i, seg in enumerate(data.get("segments", []), 1):
            start = seconds_to_srt_timestamp(seg["start"])
            end = seconds_to_srt_timestamp(seg["end"])
            parts.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}")
        return "\n\n".join(parts)
    if response_format == "vtt":
        parts = ["WEBVTT"]
        for seg in data.get("segments", []):
            start = seconds_to_vtt_timestamp(seg["start"])
            end = seconds_to_vtt_timestamp(seg["end"])
            parts.append(f"\n{start} --> {end}\n{seg['text'].strip()}")
        return "\n".join(parts)
    return data.get("text", "").strip()


# ── Chunk-Merge ────────────────────────────────────────────────────────────────

def _offset_srt_ts(ts: str, offset_sec: float) -> str:
    """Shift an SRT timestamp (HH:MM:SS,mmm) by offset_sec."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
    total_ms = max(0, total_ms + int(offset_sec * 1000))
    h2, total_ms = divmod(total_ms, 3_600_000)
    m2, total_ms = divmod(total_ms, 60_000)
    s2, ms2 = divmod(total_ms, 1000)
    return f"{h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}"


def merge_srt(chunks: list[tuple[str, float]]) -> str:
    """Merge SRT chunks, shifting timestamps and renumbering entries."""
    entries: list[tuple[str, str, str]] = []
    for text, offset in chunks:
        for block in re.split(r"\n\n+", text.strip()):
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
            if not m:
                continue
            entries.append((_offset_srt_ts(m.group(1), offset), _offset_srt_ts(m.group(2), offset), "\n".join(lines[2:])))
    return "\n".join(f"{i}\n{s} --> {e}\n{c}\n" for i, (s, e, c) in enumerate(entries, 1))


def _offset_vtt_ts(ts: str, offset_sec: float) -> str:
    """Shift a VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) by offset_sec."""
    parts = ts.split(":")
    h, m, s_ms = (parts[0], parts[1], parts[2]) if len(parts) == 3 else ("0", parts[0], parts[1])
    s, ms = s_ms.split(".")
    total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
    total_ms = max(0, total_ms + int(offset_sec * 1000))
    h2, total_ms = divmod(total_ms, 3_600_000)
    m2, total_ms = divmod(total_ms, 60_000)
    s2, ms2 = divmod(total_ms, 1000)
    return f"{h2:02d}:{m2:02d}:{s2:02d}.{ms2:03d}"


def merge_vtt(chunks: list[tuple[str, float]]) -> str:
    """Merge VTT chunks, shifting timestamps."""
    cues: list[str] = []
    for text, offset in chunks:
        lines = text.splitlines()
        # skip WEBVTT header line(s)
        i = 0
        while i < len(lines) and not re.search(r"-->", lines[i]):
            i += 1
        cue_lines: list[str] = []
        for line in lines[i:]:
            m = re.match(r"([\d:]+\.?\d*)\s+-->\s+([\d:]+\.?\d*)(.*)", line)
            if m:
                if cue_lines:
                    cues.append("\n".join(cue_lines))
                    cue_lines = []
                cue_lines.append(f"{_offset_vtt_ts(m.group(1), offset)} --> {_offset_vtt_ts(m.group(2), offset)}{m.group(3)}")
            else:
                cue_lines.append(line)
        if cue_lines:
            cues.append("\n".join(cue_lines))
    return "WEBVTT\n\n" + "\n\n".join(c.strip() for c in cues if c.strip())
