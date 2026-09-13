"""Podcast audio assembly carries the AI notice in the finished MP3."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.features.podcast.audio import kleben
from src.services.ai_hinweis import AI_HINWEIS_TEXT

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _tonschnipsel() -> bytes:
    # Written to a real file (not piped) so the encoder can seek back and
    # write a Xing/LAME header, matching real voiced pieces on disk. A piped
    # "-f mp3 pipe:1" stream lacks that header and trips an unrelated
    # libmp3lame concat bug ("inadequate AVFrame plane padding") in this
    # container's ffmpeg build.
    with tempfile.TemporaryDirectory(prefix="ai_hinweis_test_") as tmpdir:
        datei = Path(tmpdir) / "stueck.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "1", "-c:a", "libmp3lame", "-q:a", "4", str(datei)],
            capture_output=True, check=True,
        )
        return datei.read_bytes()


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_der_fertige_podcast_traegt_den_ki_hinweis(tmp_path):
    stueck = _tonschnipsel()
    audio_bytes, _dauer = kleben([stueck, stueck], pause=0.2)
    datei = tmp_path / "podcast.mp3"
    datei.write_bytes(audio_bytes)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
         "-of", "default=nw=1:nk=1", str(datei)],
        capture_output=True, text=True, check=True,
    )
    assert AI_HINWEIS_TEXT in result.stdout
