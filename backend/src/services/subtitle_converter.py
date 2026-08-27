"""WebVTT subtitles: write segments to VTT, split them and read VTT back."""

from __future__ import annotations

import re

# Broadcast standard limits for one cue.
MAX_ZEICHEN_JE_ZEILE = 42
MAX_ZEILEN_JE_EINBLENDUNG = 2

_SATZENDE = re.compile(r"(?<=[.!?])\s+")



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




def _zeilen(text: str, max_zeile: int) -> list[str]:
    """Packs words into lines, a single overlong word stays whole."""
    zeilen: list[str] = []
    aktuell = ""
    for wort in text.split():
        kandidat = f"{aktuell} {wort}" if aktuell else wort
        if aktuell and len(kandidat) > max_zeile:
            zeilen.append(aktuell)
            aktuell = wort
        else:
            aktuell = kandidat
    if aktuell:
        zeilen.append(aktuell)
    return zeilen


def _stuecke(text: str, max_zeile: int, max_zeilen: int) -> list[str]:
    """Splits text into cues, preferably at sentence ends."""
    teile: list[list[str]] = []
    for satz in _SATZENDE.split(text):
        if not satz.strip():
            continue
        zeilen = _zeilen(satz, max_zeile)
        for i in range(0, len(zeilen), max_zeilen):
            teile.append(zeilen[i:i + max_zeilen])
    zusammen: list[list[str]] = []
    for teil in teile:
        # Two short sentences may share one cue.
        if zusammen and len(zusammen[-1]) + len(teil) <= max_zeilen:
            zusammen[-1] = zusammen[-1] + teil
        else:
            zusammen.append(teil)
    return ["\n".join(t) for t in zusammen]


def split_long_segments(
    segments: list[dict],
    max_zeile: int = MAX_ZEICHEN_JE_ZEILE,
    max_zeilen: int = MAX_ZEILEN_JE_EINBLENDUNG,
) -> list[dict]:
    """Splits long segments into short cues, the time shared by character count."""
    heraus: list[dict] = []
    for seg in segments:
        text = " ".join(str(seg.get("text", "")).split())
        if not text:
            continue
        zeilen = _zeilen(text, max_zeile)
        if len(zeilen) <= max_zeilen:
            heraus.append({**seg, "text": "\n".join(zeilen)})
            continue
        stuecke = _stuecke(text, max_zeile, max_zeilen)
        gesamt = sum(len(s) for s in stuecke)
        start, ende = float(seg["start"]), float(seg["end"])
        spanne = ende - start
        gelaufen = 0
        grenze = start
        for i, stueck in enumerate(stuecke):
            gelaufen += len(stueck)
            naechste = ende if i == len(stuecke) - 1 else start + spanne * gelaufen / gesamt
            heraus.append({**seg, "start": grenze, "end": naechste, "text": stueck})
            grenze = naechste
    return heraus
