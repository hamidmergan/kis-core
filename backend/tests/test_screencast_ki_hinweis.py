"""KI-Hinweis im Screencast: Rahmen um die Folien und Kennzeichnung in der Datei."""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.services.screencast.outro import KI_HINWEIS, rahme_clips
from src.services.screencast.video import apply_faststart

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ── Reihenfolge der Clips ───────────────────────────────────────────────────


def test_der_hinweis_rahmt_die_folien_vorne_und_hinten():
    hinweis = Path("hinweis.mp4")
    folien = [Path("a.mp4"), Path("b.mp4")]
    clips, _ = rahme_clips(folien, [True, True], hinweis)
    assert clips == [hinweis, folien[0], folien[1], hinweis]


def test_der_hinweis_zaehlt_als_stumme_folie():
    clips, hat_sprache = rahme_clips([Path("a.mp4")], [True], Path("hinweis.mp4"))
    assert hat_sprache == [False, True, False]
    assert len(hat_sprache) == len(clips)


def test_ohne_hinweis_bleiben_die_folien_unberuehrt():
    folien = [Path("a.mp4")]
    clips, hat_sprache = rahme_clips(folien, [True], None)
    assert clips == folien
    assert hat_sprache == [True]


# ── Kennzeichnung in der Videodatei ─────────────────────────────────────────


@pytest.fixture
def clip(tmp_path):
    p = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "color=c=white:s=160x120:d=2",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)],
        check=True, capture_output=True,
    )
    return p


def _kommentar(path: Path) -> str:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_das_fertige_video_traegt_den_hinweis_in_der_datei(tmp_path, clip):
    fertig = tmp_path / "fertig.mp4"
    apply_faststart(clip, fertig)
    assert KI_HINWEIS in _kommentar(fertig)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_der_hinweis_steht_auch_mit_untertitel_spur_drin(tmp_path, clip):
    spur = tmp_path / "untertitel.vtt"
    spur.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHallo\n", encoding="utf-8")
    fertig = tmp_path / "fertig.mp4"
    apply_faststart(clip, fertig, subtitle_path=spur, subtitle_lang="deu")
    assert KI_HINWEIS in _kommentar(fertig)
