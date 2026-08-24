"""Die Länge einer zusammengeklebten MP3 darf nicht geschätzt werden."""

import shutil
import subprocess

import pytest

from src.services.screencast.video import create_slide_video, get_audio_duration

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _bild_sekunden(path) -> float:
    """Länge des Containers, also wie lange das Bild steht."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _ton_sekunden(path) -> float:
    """Echte Länge über die dekodierten Abtastwerte, ohne Container-Angabe."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
         "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
        capture_output=True, check=True,
    )
    return len(result.stdout) / 2 / 48000


def _mp3(path, sekunden: float, bitrate: str, frequenz: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"sine=frequency={frequenz}:duration={sekunden}",
         "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", "24000", "-ac", "1", str(path)],
        check=True,
    )


@pytest.fixture
def geklebte_mp3(tmp_path):
    """Zwei Stücke mit verschiedener Bitrate, roh aneinander wie in synthesize()."""
    erstes, zweites = tmp_path / "a.mp3", tmp_path / "b.mp3"
    _mp3(erstes, 5.0, "128k", 440)
    _mp3(zweites, 5.0, "32k", 660)
    geklebt = tmp_path / "geklebt.mp3"
    geklebt.write_bytes(erstes.read_bytes() + zweites.read_bytes())
    return geklebt


def test_stumme_folie_bleibt_bei_drei_sekunden():
    assert get_audio_duration(None) == 3.0


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_geklebte_mp3_wird_nicht_zu_kurz_gemessen(geklebte_mp3):
    """Zu kurz gemessen heißt abgeschnittener Ton, zu lang fängt -shortest ab."""
    echt = _ton_sekunden(geklebte_mp3)
    assert get_audio_duration(geklebte_mp3) >= echt - 0.05


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_einzelne_datei_wird_weiter_richtig_gemessen(tmp_path):
    einzeln = tmp_path / "einzeln.mp3"
    _mp3(einzeln, 4.0, "64k", 440)
    assert get_audio_duration(einzeln) == pytest.approx(_ton_sekunden(einzeln), abs=0.1)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_nicht_messbare_datei_wird_nicht_geschaetzt(tmp_path):
    """Lieber abbrechen als raten, wann eine Folie zu Ende ist."""
    with pytest.raises(RuntimeError):
        get_audio_duration(tmp_path / "gibtsnicht.mp3")


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_clip_behaelt_den_ganzen_ton(tmp_path, geklebte_mp3):
    """Der Weg, auf dem im echten Video Wörter verschwunden sind."""
    bild = tmp_path / "folie.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=white:s=320x240:d=1", "-frames:v", "1", str(bild)],
        check=True,
    )
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, geklebte_mp3, clip, pause=0.5, crf=30)
    soll = _ton_sekunden(geklebte_mp3) + 0.5
    ist = _ton_sekunden(clip)
    assert ist >= soll - 0.02, "Ton wurde abgeschnitten"
    assert ist <= soll + 0.3, "Clip läuft unerwartet lange nach"


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_clip_ohne_pause_behaelt_den_ganzen_ton(tmp_path, geklebte_mp3):
    bild = tmp_path / "folie.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=white:s=320x240:d=1", "-frames:v", "1", str(bild)],
        check=True,
    )
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, geklebte_mp3, clip, pause=0.0, crf=30)
    soll = _ton_sekunden(geklebte_mp3)
    ist = _ton_sekunden(clip)
    assert ist >= soll - 0.02, "Ton wurde abgeschnitten"
    assert ist <= soll + 0.3, "Clip läuft unerwartet lange nach"


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_bild_steht_nicht_laenger_als_der_ton(tmp_path, geklebte_mp3):
    """Sonst friert die Folie ein und die nächste kommt zu spät."""
    bild = tmp_path / "folie.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=white:s=320x240:d=1", "-frames:v", "1", str(bild)],
        check=True,
    )
    clip = tmp_path / "clip.mp4"
    create_slide_video(bild, geklebte_mp3, clip, pause=0.5, crf=30)
    assert _bild_sekunden(clip) <= _ton_sekunden(clip) + 0.3


def _hat_bildspur(path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v",
         "-show_entries", "stream=nb_frames", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


@pytest.fixture
def folienbild(tmp_path):
    bild = tmp_path / "folie.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=white:s=320x240:d=1", "-frames:v", "1", str(bild)],
        check=True,
    )
    return bild


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_sehr_kurze_folie_bekommt_ein_bild(tmp_path, folienbild):
    """Ohne Bildspur zerlegt die Folie beim Zusammenfügen das ganze Video."""
    kurz = tmp_path / "kurz.mp3"
    _mp3(kurz, 0.5, "64k", 440)
    clip = tmp_path / "clip.mp4"
    create_slide_video(folienbild, kurz, clip, pause=0.0, crf=30)
    assert _hat_bildspur(clip)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_kurze_folie_verschiebt_den_folienwechsel_nicht(tmp_path, folienbild):
    from src.services.screencast.video import concatenate_videos

    kurz, lang = tmp_path / "kurz.mp3", tmp_path / "lang.mp3"
    _mp3(kurz, 0.5, "64k", 440)
    _mp3(lang, 4.0, "64k", 660)
    clips = []
    for n, ton in enumerate((lang, kurz, lang)):
        clip = tmp_path / f"clip_{n}.mp4"
        create_slide_video(folienbild, ton, clip, pause=0.0, crf=30)
        clips.append(clip)
    verbund = tmp_path / "verbund.mp4"
    concatenate_videos(clips, verbund)
    soll = sum(_ton_sekunden(c) for c in clips)
    assert _ton_sekunden(verbund) == pytest.approx(soll, abs=0.2)
    assert _bild_sekunden(verbund) <= soll + 0.3
