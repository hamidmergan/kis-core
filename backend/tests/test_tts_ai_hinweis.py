# backend/tests/test_tts_ai_hinweis.py
"""The finished TTS audio carries the AI notice in its metadata."""

import shutil
import subprocess

import pytest

from src.services.ai_hinweis import AI_HINWEIS_TEXT
from src.tasks.tts_tasks import _stamped_with_ai_notice

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _stiller_ton() -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "1", "-c:a", "libmp3lame", "-q:a", "4", "-f", "mp3", "pipe:1"],
        capture_output=True, check=True,
    )
    return result.stdout


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_die_fertige_mp3_traegt_den_ki_hinweis(tmp_path):
    stamped = _stamped_with_ai_notice(_stiller_ton())
    datei = tmp_path / "fertig.mp3"
    datei.write_bytes(stamped)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
         "-of", "default=nw=1:nk=1", str(datei)],
        capture_output=True, text=True, check=True,
    )
    assert AI_HINWEIS_TEXT in result.stdout
