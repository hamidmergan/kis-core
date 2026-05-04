"""Audio chunking utilities for Whisper uploads.

OpenAI-compatible Whisper deployments accept max 600s per upload. Longer audio
is split at silence points, transcribed individually and stitched back together.
All functions here are pure (no client state)."""

import json
import re
import subprocess
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────
CHUNK_MAX_SEC = 540        # 9 min - safely under the typical 600s upload limit
MAX_AUDIO_SEC = 12000      # 200 min, hard upload limit
CHUNK_REENCODE_BITRATE_KBPS = 64  # 64 kbps mono mp3 → ~4 MB / 9-min chunk; bypass nginx upload limits (e.g. myLab 413)
CHUNK_REENCODE_SAMPLE_RATE_HZ = 16000  # Whisper resamples to 16 kHz internally — match it to skip server-side conversion
_SILENCE_NOISE_DB = -40    # dB threshold for silence detection
_SILENCE_MIN_DURATION = 0.3  # Minimum silence duration (s)
_SPLIT_SEARCH_WINDOW = 60  # Search window around each target split point (s)


def get_audio_duration(file_path: str) -> float:
    """Return audio/video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if duration:
            return float(duration)
    fmt_duration = data.get("format", {}).get("duration")
    if fmt_duration:
        return float(fmt_duration)
    raise RuntimeError("Could not determine audio duration via ffprobe")


def find_silence_starts(file_path: str) -> list[float]:
    """Run ffmpeg silencedetect and return a list of silence_start timestamps."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-af", f"silencedetect=noise={_SILENCE_NOISE_DB}dB:d={_SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    output = result.stderr + result.stdout
    return [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([\d.]+)", output)]


def compute_split_points(duration: float, silence_starts: list[float]) -> list[float]:
    """Return split timestamps aligned to nearby silence points."""
    split_points: list[float] = []
    target = CHUNK_MAX_SEC
    while target < duration - 10:
        window_min = target - _SPLIT_SEARCH_WINDOW
        window_max = target + _SPLIT_SEARCH_WINDOW
        candidates = [s for s in silence_starts if window_min <= s <= window_max]
        best = min(candidates, key=lambda s: abs(s - target)) if candidates else target
        split_points.append(best)
        target = best + CHUNK_MAX_SEC
    return split_points


def split_audio(file_path: str, split_points: list[float], tmpdir: str) -> list[tuple[str, float]]:
    """Split audio at given timestamps and re-encode to low-bitrate mono mp3.

    Re-encoding (instead of stream-copy) keeps every chunk under typical Whisper
    upload limits regardless of source bitrate or codec (see CHUNK_REENCODE_BITRATE_KBPS).

    Returns list of (chunk_path, start_offset_seconds).
    """
    boundaries = [0.0] + split_points + [None]  # None = end of file
    chunks: list[tuple[str, float]] = []
    for i, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        chunk_path = str(Path(tmpdir) / f"chunk_{i:03d}.mp3")
        cmd = ["ffmpeg", "-i", file_path, "-ss", str(start)]
        if end is not None:
            cmd += ["-to", str(end)]
        cmd += [
            "-vn",                           # drop video stream
            "-c:a", "libmp3lame",
            "-b:a", f"{CHUNK_REENCODE_BITRATE_KBPS}k",
            "-ac", "1",                      # mono
            "-ar", str(CHUNK_REENCODE_SAMPLE_RATE_HZ),
            "-y", chunk_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed for chunk {i}: {result.stderr[:200]}")
        chunks.append((chunk_path, start))
    return chunks
