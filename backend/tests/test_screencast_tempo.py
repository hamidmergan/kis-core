"""The speed is applied locally, the provider would lower the pitch with it."""

import shutil
import subprocess

import pytest

from src.services.screencast.video import create_slide_video

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _ton_sekunden(path) -> float:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
         "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
        capture_output=True, check=True,
    )
    return len(result.stdout) / 2 / 48000


@pytest.fixture
def bild(tmp_path):
    p = tmp_path / "folie.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=white:s=320x240:d=1", "-frames:v", "1", str(p)],
        check=True,
    )
    return p


@pytest.fixture
def ton(tmp_path):
    p = tmp_path / "ton.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1", str(p)],
        check=True,
    )
    return p


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_tempo_eins_laesst_den_ton_unveraendert(tmp_path, bild, ton):
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, ton, clip, pause=0.0, crf=30, speed=1.0)
    assert _ton_sekunden(clip) == pytest.approx(_ton_sekunden(ton), abs=0.15)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_langsameres_tempo_verlaengert_den_ton(tmp_path, bild, ton):
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, ton, clip, pause=0.0, crf=30, speed=0.9)
    assert _ton_sekunden(clip) == pytest.approx(_ton_sekunden(ton) / 0.9, abs=0.2)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_die_pause_wird_nicht_mitgedehnt(tmp_path, bild, ton):
    """The pause is a value in seconds, not part of the recording."""
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, ton, clip, pause=1.0, crf=30, speed=0.5)
    soll = _ton_sekunden(ton) / 0.5 + 1.0
    assert _ton_sekunden(clip) == pytest.approx(soll, abs=0.3)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_schnelleres_tempo_verkuerzt_den_ton(tmp_path, bild, ton):
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, ton, clip, pause=0.0, crf=30, speed=1.2)
    assert _ton_sekunden(clip) == pytest.approx(_ton_sekunden(ton) / 1.2, abs=0.2)
