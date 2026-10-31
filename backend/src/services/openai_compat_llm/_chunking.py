"""Splits long recordings at speech pauses for the Whisper upload."""

import json
import os
import re
import subprocess
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────
CHUNK_MAX_SEC = 540        # 9 min - safely under the typical 600s upload limit
CHUNK_REENCODE_BITRATE_KBPS = 64  # 64 kbps mono mp3 → ~4 MB / 9-min chunk; bypass nginx upload limits (e.g. myLab 413)
CHUNK_REENCODE_SAMPLE_RATE_HZ = 16000  # Whisper resamples to 16 kHz internally — match it to skip server-side conversion
CHUNK_MAX_DIRECT_BYTES = 20 * 1024 * 1024  # Whisper rejects uploads above ~25 MB, leave room
_SILENCE_NOISE_DB = -40    # dB threshold for silence detection
_SILENCE_MIN_DURATION = 0.3  # Minimum silence duration (s)
_SPLIT_SEARCH_WINDOW = 60  # Search window around each target split point (s)


class AudioTooLongError(Exception):
    """Recording longer than allowed, the limit comes in as an argument."""

    def __init__(self, duration_sec: float, max_sec: int):
        self.duration_sec = duration_sec
        self.max_sec = max_sec
        super().__init__(
            f"Audio too long ({duration_sec / 60:.1f} min), maximum {max_sec // 60} min"
        )


class NoAudioTrackError(ValueError):
    """Video without a sound track, there is nothing to recognise."""


def get_audio_duration(file_path: str) -> float:
    """Return audio/video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
    data = json.loads(result.stdout)
    if not any(s.get("codec_type") == "audio" for s in data.get("streams", [])):
        raise NoAudioTrackError("Media file has no audio stream")
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if duration:
            return float(duration)
    fmt_duration = data.get("format", {}).get("duration")
    if fmt_duration:
        return float(fmt_duration)
    raise RuntimeError("Could not determine audio duration via ffprobe")


def find_silence_starts(file_path: str) -> list[float]:
    """Finds the speech pauses via ffmpeg, without decoding the video track."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-vn",
            "-af", f"silencedetect=noise={_SILENCE_NOISE_DB}dB:d={_SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    output = result.stderr + result.stdout
    return [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([\d.]+)", output)]


def fits_single_upload(file_path: str, duration: float) -> bool:
    """True when the file is short and small enough to go to Whisper as it is."""
    return duration <= CHUNK_MAX_SEC and os.path.getsize(file_path) <= CHUNK_MAX_DIRECT_BYTES


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
    """Cuts the recording and turns every piece into a small MP3."""
    boundaries = [0.0] + split_points + [None]  # None = end of file
    chunks: list[tuple[str, float]] = []
    for i, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        chunk_path = str(Path(tmpdir) / f"chunk_{i:03d}.mp3")
        cmd = ["ffmpeg", "-ss", str(start), "-i", file_path]
        if end is not None:
            cmd += ["-t", str(end - start)]  # duration, not absolute end (input-seek relative)
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
