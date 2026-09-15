"""Ist die Etappe vorbei, werden nur noch begonnene Folien fertig gesprochen."""

import asyncio

from src.services.screencast.generation import generate_all_tts
from src.tasks._stage import StageClock

from tests.test_screencast_tts_reihenfolge import FakeTts, LANG


class _Uhr:
    """Laeuft nach der angegebenen Zahl von Abfragen ab."""

    def __init__(self, nach: int):
        self.rest = nach

    def over(self) -> bool:
        if self.rest <= 0:
            return True
        self.rest -= 1
        return False

    def spent(self) -> float:
        return 0.0


def _lauf(scripts, tmp_path, clock=None, on_beat=None):
    tts = FakeTts()
    gemeldet: list[int] = []
    asyncio.run(generate_all_tts(
        scripts, tts, tmp_path, 1.0, voice_id="alloy",
        on_slide_done=lambda current, total, folie: gemeldet.append(folie),
        clock=clock, on_beat=on_beat,
    ))
    return gemeldet, tts


def test_ohne_uhr_werden_alle_folien_gesprochen(tmp_path):
    gemeldet, _tts = _lauf(["Eins.", "Zwei.", "Drei."], tmp_path)
    assert gemeldet == [0, 1, 2]


def test_eine_abgelaufene_uhr_beginnt_keine_neue_folie(tmp_path):
    _gemeldet, tts = _lauf(["Eins.", "Zwei.", "Drei."], tmp_path, clock=StageClock(seconds=0))
    assert tts.anfragen == 0


def test_eine_begonnene_folie_wird_zu_ende_gesprochen(tmp_path):
    """Die Uhr laeuft nach dem ersten Stueck ab, die restlichen Stuecke derselben Folie bleiben."""
    _gemeldet, tts = _lauf([LANG], tmp_path, clock=_Uhr(nach=1))
    datei = tmp_path / "slide_000.mp3"
    assert datei.exists()
    assert tts.anfragen > 1


def test_nicht_erreichte_folien_haben_keine_datei(tmp_path):
    _lauf(["Eins.", "Zwei.", "Drei."], tmp_path, clock=_Uhr(nach=1))
    assert (tmp_path / "slide_000.mp3").exists()
    assert not (tmp_path / "slide_002.mp3").exists()


def test_eine_verkehrt_fertige_folie_gibt_trotzdem_ein_lebenszeichen(tmp_path):
    """Folie 1 wird vor Folie 0 fertig, freigegeben wird nichts, gemeldet werden muss es doch."""
    schlaege = []
    # Die lange Folie 0 haelt die Freigabe auf, die kurze Folie 1 ist vorher fertig.
    _lauf([LANG, "Kurz."], tmp_path, on_beat=lambda: schlaege.append(1))
    assert schlaege
