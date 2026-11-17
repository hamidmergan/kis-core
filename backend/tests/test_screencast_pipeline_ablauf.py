"""The render pipeline end to end with every outside call faked: order of the steps and what is stored."""

import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.tasks._stage import StageContinue
from src.tasks.screencast_tasks import _pipeline
from src.tasks.screencast_tasks._shared import _JobCancelled

UUID = "c" * 32


class _OhneWaechter:
    """The cancel watcher would otherwise query the real Redis."""

    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


@pytest.fixture
def strecke(monkeypatch, tmp_path):
    """Runs the pipeline over two slides and records what it did."""
    ablauf: list = []
    ablage: dict = {}
    schalter = SimpleNamespace(ohne_ton=set(), abbruch_bei=None)

    async def sprechen(scripts, client, tmp, speed, voice_id, on_slide_done=None, **kw):
        ergebnis = []
        for i, _ in enumerate(scripts):
            pfad = tmp / f"audio_{i}.mp3"
            if i not in schalter.ohne_ton:
                pfad.write_bytes(b"ton%d" % i)
                on_slide_done(i + 1, len(scripts), i)
            ergebnis.append((pfad, 1.0))
        return ergebnis

    def clip(bild, ton, ziel, **kw):
        ablauf.append(("clip", Path(ziel).name, kw.get("silent_duration")))
        Path(ziel).write_bytes(b"clip")

    def kleben(clips, ziel):
        ablauf.append(("concat", [Path(c).name for c in clips]))

    def faststart(quelle, ziel, spur, sprache):
        ablauf.append(("faststart", spur, sprache))
        return b"video"

    @contextmanager
    def messe(user_id, job_uuid, name):
        ablauf.append(("messe", name))
        yield {}

    @contextmanager
    def herzschlag(job_uuid):
        yield

    def status(job_uuid, zustand, progress=None, **kw):
        ablauf.append(("status", (progress or {}).get("step")))
        if schalter.abbruch_bei == (progress or {}).get("step"):
            raise _JobCancelled()

    def kein_stand(user_id, job_uuid, name):
        raise FileNotFoundError(name)

    helfer = (tmp_path / "bilder", None, sprechen, None, clip, kleben, faststart, None,
              lambda w, h, pfad: Path(pfad).write_bytes(b"png"), lambda bild: (16, 9))
    monkeypatch.setattr(_pipeline, "threading", SimpleNamespace(Event=threading.Event, Thread=_OhneWaechter))
    monkeypatch.setattr(_pipeline, "_get_screencast_helpers", lambda: helfer)
    monkeypatch.setattr(_pipeline, "_get_tts_client", lambda pid, user_id=None: object())
    monkeypatch.setattr(_pipeline, "_assert_not_cancelled", lambda j: None)
    monkeypatch.setattr(_pipeline, "still_mine", lambda j, token: True)
    monkeypatch.setattr(_pipeline, "job_heartbeat", herzschlag)
    monkeypatch.setattr(_pipeline.db, "get_job", lambda j: {"user_id": 1})
    monkeypatch.setattr(_pipeline.db, "update_job_status", status)
    monkeypatch.setattr(_pipeline.db, "set_render_started_at", lambda j: ablauf.append(("render_started",)))
    monkeypatch.setattr(_pipeline.db, "touch_job_heartbeat", lambda j: None)
    monkeypatch.setattr(_pipeline, "get_job_file", kein_stand)
    monkeypatch.setattr(_pipeline, "save_job_file", lambda u, j, name, daten: ablage.__setitem__(name, daten))
    monkeypatch.setattr(_pipeline, "clear_render_cache", lambda u, j: ablauf.append(("cache_geleert",)))
    monkeypatch.setattr(_pipeline, "audio_folien_mit_ton", lambda u, j: set())
    monkeypatch.setattr(_pipeline, "load_result_meta", lambda u, j: {"target_lang": "EN-US", "alt": 1})
    monkeypatch.setattr(_pipeline, "messe", messe)
    monkeypatch.setattr(_pipeline, "anbieter_und_modell", lambda pid, f: {})
    monkeypatch.setattr(_pipeline, "save_audio_cache", lambda u, j, ton: ablage.__setitem__("ton", ton))
    monkeypatch.setattr(_pipeline, "save_result_file", lambda u, j, ext, daten: f"ergebnis{ext}")
    monkeypatch.setattr(_pipeline, "save_result_meta", lambda u, j, meta: ablage.__setitem__("meta", meta))

    bilder = []
    for i in range(2):
        bild = tmp_path / f"slide-{i}.png"
        bild.write_bytes(b"png")
        bilder.append(bild)

    def lauf(**kw):
        return _pipeline._run_render_pipeline(
            job_uuid=UUID, scripts=["Eins.", "Zwei."], voice_id="nova", speed=1.0, slide_pause=1.0,
            slide_images_override=bilder, provider_id=21, voice_label="Nova", **kw)

    return SimpleNamespace(ablauf=ablauf, ablage=ablage, schalter=schalter, lauf=lauf)


def test_the_steps_run_in_their_order_and_the_result_is_stored(strecke):
    ergebnis = strecke.lauf()
    assert ergebnis == {"result_path": "ergebnis.mp4", "audio_id": UUID, "audio_count": 2}
    assert [e[1] for e in strecke.ablauf if e[0] == "status"] == [
        "images", "tts", "tts", "tts", "video", "video", "video", "concat", "faststart", "saving"]
    assert [e[1] for e in strecke.ablauf if e[0] == "messe"] == ["bilder", "vertonung", "clips", "zusammenfuegen"]
    # The notice clip frames the slides, it is the only silent one.
    assert ("clip", "clip_ki_hinweis.mp4", 3.0) in strecke.ablauf
    assert ("concat", ["clip_ki_hinweis.mp4", "clip_000.mp4", "clip_001.mp4", "clip_ki_hinweis.mp4"]) in strecke.ablauf
    assert ("faststart", None, "") in strecke.ablauf
    assert strecke.ablage["ton"] == [b"ton0", b"ton1"]
    assert strecke.ablage["meta"] == {"target_lang": "EN-US", "alt": 1, "audio_id": UUID, "audio_count": 2,
                                      "subtitles": False, "video_folien": [0, 1]}
    assert {"render_params.json", "render_scripts.json"} <= set(strecke.ablage)


def test_subtitles_get_their_own_track_after_the_notice_clip(strecke, monkeypatch, tmp_path):
    from src.services.screencast import subtitles

    gesehen = {}

    def spur(clips, tmp, hat_sprache):
        gesehen["hat_sprache"] = hat_sprache
        pfad = tmp / "spur.vtt"
        pfad.write_bytes(b"WEBVTT")
        return pfad

    monkeypatch.setattr(subtitles, "create_subtitle_track", spur)
    strecke.lauf(subtitles=True)
    assert gesehen["hat_sprache"] == [False, True, True, False]
    assert strecke.ablage["untertitel.vtt"] == b"WEBVTT"
    assert strecke.ablage["meta"]["subtitles"] is True
    faststart = next(e for e in strecke.ablauf if e[0] == "faststart")
    assert faststart[1].name == "spur.vtt" and faststart[2] == "eng"
    schritte = [e[1] for e in strecke.ablauf if e[0] == "status"]
    assert schritte.index("subtitles") < schritte.index("concat")


def test_a_slide_the_stage_did_not_voice_hands_the_run_to_the_next_stage(strecke):
    strecke.schalter.ohne_ton = {1}
    with pytest.raises(StageContinue):
        strecke.lauf()
    assert "video" not in [e[1] for e in strecke.ablauf if e[0] == "status"]
    assert "ton" not in strecke.ablage


def test_only_the_chosen_slides_become_clips(strecke):
    ergebnis = strecke.lauf(video_folien=[1])
    assert ergebnis["audio_count"] == 2
    assert ("concat", ["clip_ki_hinweis.mp4", "clip_000.mp4", "clip_ki_hinweis.mp4"]) in strecke.ablauf
    assert strecke.ablage["meta"]["video_folien"] == [1]


def test_a_cancel_during_the_clips_stops_before_anything_is_stored(strecke):
    strecke.schalter.abbruch_bei = "concat"
    with pytest.raises(_JobCancelled):
        strecke.lauf()
    assert "ton" not in strecke.ablage and "meta" not in strecke.ablage
