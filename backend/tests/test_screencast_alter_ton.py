"""Only ticked slides are spoken again, the rest comes from audio/."""

import asyncio

import pytest

from src.services.screencast.generation import generate_all_tts

UUID = "c" * 32
TEXT = "Ein kurzer Satz."


class FakeTts:
    def __init__(self):
        self.gesprochen: list[str] = []

    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        self.gesprochen.append(text)
        return {"audio_bytes": b"ID3neu", "alignment": None}


def _lauf(tmp_path, scripts, dateien, **kw):
    def hole(user_id, job_uuid, name):
        if name not in dateien:
            raise FileNotFoundError(name)
        return dateien[name]

    tts = FakeTts()
    import src.services.screencast.generation as g
    alt_get, alt_save = g.get_job_file, g.save_job_file
    g.get_job_file = hole
    g.save_job_file = lambda *a, **k: None
    try:
        ergebnis = asyncio.run(generate_all_tts(
            scripts, tts, tmp_path, 1.0, voice_id="alloy",
            job_uuid=UUID, user_id=1, **kw,
        ))
    finally:
        g.get_job_file, g.save_job_file = alt_get, alt_save
    return tts, ergebnis


def test_ohne_erlaubnis_wird_neu_gesprochen(tmp_path):
    """The default is the old one: audio/ is not touched."""
    tts, _ = _lauf(tmp_path, [TEXT], {"audio/slide_000.mp3": b"ID3alt"})
    assert tts.gesprochen == [TEXT]


def test_mit_erlaubnis_kommt_der_alte_ton(tmp_path):
    tts, ergebnis = _lauf(
        tmp_path, [TEXT], {"audio/slide_000.mp3": b"ID3alt"},
        alter_ton_erlaubt={0},
    )
    assert tts.gesprochen == []
    assert ergebnis[0][0].read_bytes() == b"ID3alt"


def test_der_vorrat_schlaegt_den_alten_ton(tmp_path):
    """Otherwise a retry loses the slide it just spoke."""
    _, ergebnis = _lauf(
        tmp_path, [TEXT],
        {"render_cache/slide_000.mp3": b"ID3vorrat", "audio/slide_000.mp3": b"ID3alt"},
        alter_ton_erlaubt={0},
    )
    assert ergebnis[0][0].read_bytes() == b"ID3vorrat"


def test_leere_datei_im_audio_ordner_zaehlt_nicht(tmp_path):
    tts, _ = _lauf(
        tmp_path, [TEXT], {"audio/slide_000.mp3": b""},
        alter_ton_erlaubt={0},
    )
    assert tts.gesprochen == [TEXT]


def test_ausgeschlossene_folie_wird_nicht_vertont(tmp_path):
    tts, ergebnis = _lauf(tmp_path, [TEXT, TEXT], {}, ausgeschlossen={1})
    assert tts.gesprochen == [TEXT]
    assert ergebnis[1][0] is None


def test_ausgeschlossene_folie_haelt_die_reihenfolge_nicht_auf(tmp_path):
    gemeldet: list[int] = []
    _lauf(tmp_path, [TEXT, TEXT, TEXT], {}, ausgeschlossen={1},
          on_slide_done=lambda current, total, folie: gemeldet.append(folie))
    assert gemeldet == [0, 1, 2]


def test_der_zaehler_meldet_den_alten_ton(tmp_path):
    zaehler: dict = {}
    _lauf(tmp_path, [TEXT, TEXT], {"audio/slide_001.mp3": b"ID3alt"},
          alter_ton_erlaubt={1}, zaehler=zaehler)
    assert zaehler["aus_altem_ton"] == 1
