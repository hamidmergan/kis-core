"""Untertitel-Spur fuer den Screencast: Zeitversatz je Folie und Spur im MP4."""

import inspect
import shutil
import subprocess
from pathlib import Path

import pytest

from src.services.screencast.subtitles import (
    build_subtitle_vtt,
    transcribe_slides,
    vtt_sprachkennung,
)
from src.services.screencast.video import apply_faststart, get_video_duration

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _vtt(start: str, ende: str, text: str) -> str:
    return f"WEBVTT\n\n{start} --> {ende}\n{text}\n"


def _seg(start: float, ende: float, text: str) -> dict:
    return {"start": start, "end": ende, "text": text}


class _FakeWhisper:
    """Antwortet je Dateiname, weil die Folien parallel erkannt werden.

    myLab kann kein vtt oder srt, nur verbose_json mit Segmenten.
    """

    def __init__(self, antworten: dict):
        self.antworten = antworten
        self.aufrufe = []

    def transcribe_verbose(self, file_path: str):
        self.aufrufe.append(file_path)
        antwort = self.antworten[Path(file_path).name]
        if isinstance(antwort, Exception):
            raise antwort
        return antwort, "de"


def test_zweite_folie_beginnt_nach_der_ersten():
    spur = build_subtitle_vtt(
        [[_seg(0.0, 2.0, "Folie eins")], [_seg(0.0, 3.0, "Folie zwei")]],
        [5.0, 4.0],
    )
    assert "00:00:00.000 --> 00:00:02.000" in spur
    assert "00:00:05.000 --> 00:00:08.000" in spur


def test_stumme_folie_verschiebt_die_folgende_trotzdem():
    spur = build_subtitle_vtt(
        [[], [_seg(0.0, 1.0, "Folie zwei")]],
        [3.0, 4.0],
    )
    assert "00:00:03.000 --> 00:00:04.000" in spur
    assert spur.count("-->") == 1


def test_mehrere_saetze_einer_folie_bleiben_getrennt():
    spur = build_subtitle_vtt([[_seg(0.0, 2.0, "Erster Satz"), _seg(2.0, 4.0, "Zweiter Satz")]], [5.0])
    assert spur.count("-->") == 2
    assert "Erster Satz" in spur
    assert "Zweiter Satz" in spur


def test_ohne_erkannten_text_bleibt_die_spur_leer():
    assert build_subtitle_vtt([[], []], [3.0, 3.0]) == ""


def test_jede_folie_wird_einzeln_erkannt(tmp_path):
    dateien = [tmp_path / "slide_000.mp3", tmp_path / "slide_001.mp3"]
    for d in dateien:
        d.write_bytes(b"x")
    client = _FakeWhisper({"slide_000.mp3": [_seg(0.0, 1.0, "eins")],
                           "slide_001.mp3": [_seg(0.0, 1.0, "zwei")]})
    ergebnis = transcribe_slides(dateien, client)
    assert len(ergebnis) == 2
    assert len(client.aufrufe) == 2


def test_stumme_folie_wird_nicht_erkannt(tmp_path):
    datei = tmp_path / "slide_001.mp3"
    datei.write_bytes(b"x")
    client = _FakeWhisper({"slide_001.mp3": [_seg(0.0, 1.0, "zwei")]})
    ergebnis = transcribe_slides([None, datei], client)
    assert ergebnis[0] == []
    assert len(client.aufrufe) == 1


def test_fehler_bei_einer_folie_kippt_nicht_den_rest(tmp_path):
    dateien = [tmp_path / "slide_000.mp3", tmp_path / "slide_001.mp3"]
    for d in dateien:
        d.write_bytes(b"x")
    client = _FakeWhisper({"slide_000.mp3": RuntimeError("Whisper weg"),
                           "slide_001.mp3": [_seg(0.0, 1.0, "zwei")]})
    ergebnis = transcribe_slides(dateien, client)
    assert ergebnis[0] == []
    assert ergebnis[1][0]["text"] == "zwei"


def test_sprachkennung_hat_drei_buchstaben():
    assert vtt_sprachkennung("DE") == "deu"
    assert vtt_sprachkennung("EN-US") == "eng"
    assert vtt_sprachkennung("") == ""


@pytest.fixture
def clip(tmp_path):
    p = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "color=c=white:s=160x120:d=4",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)],
        check=True, capture_output=True,
    )
    return p


def _spuren(path, art: str) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", art,
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return len([z for z in result.stdout.splitlines() if z.strip()])


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_clip_laenge_wird_gemessen(clip):
    assert get_video_duration(clip) == pytest.approx(4.0, abs=0.2)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_ohne_untertitel_hat_das_video_keine_textspur(tmp_path, clip):
    fertig = tmp_path / "fertig.mp4"
    apply_faststart(clip, fertig)
    assert _spuren(fertig, "s") == 0


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_untertitel_kommen_als_eigene_spur_ins_video(tmp_path, clip):
    spur = tmp_path / "untertitel.vtt"
    spur.write_text(_vtt("00:00:00.000", "00:00:02.000", "Hallo"), encoding="utf-8")
    fertig = tmp_path / "fertig.mp4"
    apply_faststart(clip, fertig, subtitle_path=spur, subtitle_lang="deu")
    assert _spuren(fertig, "s") == 1
    assert _spuren(fertig, "v") == 1
    assert _spuren(fertig, "a") == 1


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_der_untertitel_text_steht_im_video(tmp_path, clip):
    spur = tmp_path / "untertitel.vtt"
    spur.write_text(_vtt("00:00:00.000", "00:00:02.000", "Hallo Welt"), encoding="utf-8")
    fertig = tmp_path / "fertig.mp4"
    apply_faststart(clip, fertig, subtitle_path=spur, subtitle_lang="deu")
    ausgelesen = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(fertig), "-map", "0:s:0", "-f", "webvtt", "-"],
        capture_output=True, text=True, check=True,
    )
    assert "Hallo Welt" in ausgelesen.stdout


# ── Untertitel-Spur im Render-Ablauf ────────────────────────────────────────


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_die_spur_wird_als_datei_mit_versatz_abgelegt(tmp_path, clip, monkeypatch):
    from src.services.screencast import subtitles as modul

    zweiter = tmp_path / "clip2.mp4"
    shutil.copy(clip, zweiter)
    # Der Ton kommt aus dem fertigen Clip, sonst passt er bei geaenderter
    # Geschwindigkeit nicht mehr zur Cliplaenge.
    client = _FakeWhisper({"stt_000.m4a": [_seg(0.0, 1.0, "eins")],
                           "stt_001.m4a": [_seg(0.0, 1.0, "zwei")]})
    monkeypatch.setattr(modul, "_spracherkenner", lambda: client)

    spur = modul.create_subtitle_track([clip, zweiter], tmp_path)
    assert spur is not None
    text = spur.read_text(encoding="utf-8")
    assert "00:00:00.000 --> 00:00:01.000" in text
    assert "00:00:04.000 --> 00:00:05.000" in text, "die zweite Folie beginnt nach dem ersten Clip"


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
def test_stumme_folien_gehen_gar_nicht_erst_zum_erkenner(tmp_path, clip, monkeypatch):
    """Auf Stille erfindet Whisper Text, etwa ein 'you'."""
    from src.services.screencast import subtitles as modul

    zweiter = tmp_path / "clip2.mp4"
    shutil.copy(clip, zweiter)
    client = _FakeWhisper({"stt_001.m4a": [_seg(0.0, 1.0, "zwei")]})
    monkeypatch.setattr(modul, "_spracherkenner", lambda: client)

    spur = modul.create_subtitle_track([clip, zweiter], tmp_path, hat_sprache=[False, True])
    assert len(client.aufrufe) == 1
    text = spur.read_text(encoding="utf-8")
    assert "zwei" in text
    assert "00:00:04.000 --> 00:00:05.000" in text


def test_ohne_spracherkenner_gibt_es_keine_spur(tmp_path, monkeypatch):
    from src.services.screencast import subtitles as modul

    def _kaputt():
        raise RuntimeError("kein STT eingerichtet")

    monkeypatch.setattr(modul, "_spracherkenner", _kaputt)
    assert modul.create_subtitle_track([tmp_path / "a.mp4"], tmp_path) is None


def test_render_anfrage_kennt_die_untertitel_wahl():
    from src.routes.screencast._models import RenderRequest

    assert RenderRequest(scripts=[], translate_job_uuid="x", provider_id=1).subtitles is False
    assert RenderRequest(scripts=[], translate_job_uuid="x", provider_id=1, subtitles=True).subtitles is True


def test_die_warteschlange_reicht_die_untertitel_wahl_durch():
    from src.tasks.screencast_tasks._queue import _render_args
    from src.tasks.screencast_tasks._render import run_screencast_render

    params = {"voice_id": "v", "speed": 1.0, "slide_pause": 0.5, "dpi": 144,
              "provider_id": 2, "voice_label": "L", "is_admin": False, "subtitles": True}
    args = _render_args("job", ["Text"], params, "datei.pptx")
    felder = list(inspect.signature(run_screencast_render.run).parameters)
    assert args[felder.index("subtitles")] is True


def test_alte_jobs_ohne_die_wahl_laufen_ohne_untertitel():
    from src.tasks.screencast_tasks._queue import _render_args
    from src.tasks.screencast_tasks._render import run_screencast_render

    params = {"voice_id": "v", "speed": 1.0, "slide_pause": 0.5, "dpi": 144,
              "provider_id": 2, "voice_label": "L", "is_admin": False}
    args = _render_args("job", ["Text"], params, "datei.pptx")
    felder = list(inspect.signature(run_screencast_render.run).parameters)
    assert args[felder.index("subtitles")] is False


def test_wiederholen_behaelt_die_untertitel_wahl():
    from src.routes.jobs._retry import _queue_params_from_render

    assert _queue_params_from_render({"voice_id": "v", "speed": 1.0, "slide_pause": 0.5,
                                      "dpi": 144, "subtitles": True})["subtitles"] is True
    assert _queue_params_from_render({"voice_id": "v", "speed": 1.0, "slide_pause": 0.5,
                                      "dpi": 144})["subtitles"] is False


def test_die_argumente_passen_zur_task_signatur():
    """Positionsargumente: eine Verschiebung wuerde die Wahl auf ein anderes Feld legen."""
    import inspect

    from src.tasks.screencast_tasks._render import run_screencast_render
    from src.tasks.screencast_tasks._queue import _render_args

    params = {"voice_id": "v", "speed": 1.0, "slide_pause": 0.5, "dpi": 144,
              "provider_id": 2, "voice_label": "L", "is_admin": False, "subtitles": True}
    felder = list(inspect.signature(run_screencast_render.run).parameters)
    assert felder[0] == "translate_job_uuid"
    assert felder[-1] == "neu_vertonen"
    assert len(_render_args("job", ["Text"], params, "datei.pptx")) == len(felder)


def test_langes_segment_wird_zu_mehreren_einblendungen():
    """Ein Segment, das der Erkenner als Textwand liefert, wird zerlegt."""
    lang = (
        "Bei wissenschaftlichen Tagungen gibt es verschiedene Verantwortliche. "
        "Je nach Groesse der Konferenz gibt es mehrere Leiter, sogenannte Chairs. "
        "Das sind Fachleute aus dem jeweiligen Gebiet, meist Professoren und Dozenten."
    )
    spur = build_subtitle_vtt([[_seg(0.0, 20.0, lang)]], [20.0])
    assert spur.count("-->") > 1


def test_keine_zeile_der_spur_ist_zu_lang():
    lang = "Ein sehr langer Satz ohne Punkt der einfach immer weiter geht und nicht aufhoert " * 3
    spur = build_subtitle_vtt([[_seg(0.0, 20.0, lang)]], [20.0])
    for zeile in spur.splitlines():
        if "-->" in zeile or zeile.strip().isdigit() or zeile in ("WEBVTT", ""):
            continue
        assert len(zeile) <= 42, zeile


def test_geteiltes_segment_behaelt_den_folienversatz():
    """Die Stuecke der zweiten Folie liegen hinter der ersten Folie."""
    lang = "Erster Satz mit Inhalt. " * 6
    spur = build_subtitle_vtt(
        [[_seg(0.0, 2.0, "Folie eins")], [_seg(0.0, 10.0, lang)]],
        [5.0, 10.0],
    )
    zeiten = [z for z in spur.splitlines() if "-->" in z]
    assert len(zeiten) > 2
    assert zeiten[1].startswith("00:00:05.000")
    assert zeiten[-1].endswith("00:00:15.000")
