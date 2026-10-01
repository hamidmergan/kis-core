"""Podcast audio assembly carries the AI notice in the finished MP3."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.features.podcast.audio import kleben, pause_vor
from src.limits import PODCAST_PAUSES
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
    audio_bytes, _dauer = kleben([stueck, stueck])
    datei = tmp_path / "podcast.mp3"
    datei.write_bytes(audio_bytes)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
         "-of", "default=nw=1:nk=1", str(datei)],
        capture_output=True, text=True, check=True,
    )
    assert AI_HINWEIS_TEXT in result.stdout


def _ton_mit_stille(tmp_path: Path) -> bytes:
    datei = tmp_path / "ton.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=1",
         "-af", "adelay=500|500,apad=pad_dur=0.5", "-ac", "2", "-ar", "44100",
         "-c:a", "libmp3lame", "-q:a", "4", str(datei)],
        capture_output=True, check=True,
    )
    return datei.read_bytes()


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_schneidet_die_stille_um_jeden_beitrag_ab(tmp_path):
    stueck = _ton_mit_stille(tmp_path)
    _ton, dauer = kleben([stueck, stueck])
    # Two pieces of 2 s each with their silent edges, without them about 1 s each.
    assert dauer < 2.8


def test_eine_schnelle_reaktion_folgt_kurz_eine_lange_erklaerung_wirkt_nach():
    schnell, normal, lang = PODCAST_PAUSES
    assert pause_vor(20.0, 1.5) == schnell
    assert pause_vor(20.0, 8.0) == lang
    assert pause_vor(6.0, 8.0) == normal
    assert schnell < normal < lang


def _ton_mit_pegel(tmp_path: Path, name: str, lautstaerke: float) -> bytes:
    datei = tmp_path / f"{name}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=2",
         "-af", f"volume={lautstaerke}", "-ac", "2", "-ar", "44100",
         "-c:a", "libmp3lame", "-q:a", "4", str(datei)],
        capture_output=True, check=True,
    )
    return datei.read_bytes()


def _mittlerer_pegel(datei: Path, start: float, dauer: float) -> float:
    ergebnis = subprocess.run(
        ["ffmpeg", "-ss", str(start), "-t", str(dauer), "-i", str(datei),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    return float(ergebnis.stderr.split("mean_volume: ")[1].split(" dB")[0])


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_eine_leise_und_eine_laute_stimme_klingen_gleich_laut(tmp_path):
    leise = _ton_mit_pegel(tmp_path, "leise", 0.05)
    laut = _ton_mit_pegel(tmp_path, "laut", 0.6)
    ton, _dauer = kleben([leise, laut])
    datei = tmp_path / "podcast.mp3"
    datei.write_bytes(ton)
    # Both tones last 2 s, the middle of each is measured.
    assert abs(_mittlerer_pegel(datei, 0.5, 1.0) - _mittlerer_pegel(datei, 2.8, 1.0)) < 1.5
