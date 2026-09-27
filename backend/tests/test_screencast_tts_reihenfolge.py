"""The voicing reports slides finished in order, not by text length."""

import asyncio
import threading
import time

from src.services.screencast import generation
from src.services.screencast.generation import generate_all_tts

# A real slide script is 1500 to 2000 characters and splits into several pieces.
LANG = ("Dies ist ein etwas laengerer Satz ueber das Thema der Folie und seine Bedeutung. " * 24).strip()
KURZ = "Kurz und knapp."


class FakeTts:
    """Answers slowly on long pieces and measures the concurrency."""

    def __init__(self, dauer_lang: float = 0.05, dauer_kurz: float = 0.002):
        self.dauer_lang = dauer_lang
        self.dauer_kurz = dauer_kurz
        self._lock = threading.Lock()
        self._laufend = 0
        self.max_gleichzeitig = 0
        self.anfragen = 0

    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        with self._lock:
            self.anfragen += 1
            self._laufend += 1
            self.max_gleichzeitig = max(self.max_gleichzeitig, self._laufend)
        time.sleep(self.dauer_lang if len(text) > 100 else self.dauer_kurz)
        with self._lock:
            self._laufend -= 1
        return {"audio_bytes": b"mp3", "alignment": None}


def _lauf(scripts, tmp_path, tts=None):
    tts = tts or FakeTts()
    gemeldet: list[int] = []
    ergebnis = asyncio.run(generate_all_tts(
        scripts, tts, tmp_path, 1.0, voice_id="alloy",
        on_slide_done=lambda current, total, folie: gemeldet.append(folie),
    ))
    return gemeldet, tts, ergebnis


def test_lange_folie_meldet_sich_vor_den_kurzen_dahinter(tmp_path):
    """Today the short slides win because the long one sends its pieces one by one."""
    gemeldet, _, _ = _lauf([LANG, KURZ, KURZ], tmp_path)
    assert gemeldet == [0, 1, 2]


def test_reihenfolge_haelt_auch_bei_wechselnden_laengen(tmp_path):
    gemeldet, _, _ = _lauf([KURZ, LANG, KURZ, LANG, KURZ], tmp_path)
    assert gemeldet == [0, 1, 2, 3, 4]


def test_folie_ohne_text_haelt_die_reihenfolge_nicht_auf(tmp_path):
    gemeldet, _, _ = _lauf([LANG, "   ", KURZ], tmp_path)
    assert gemeldet == [0, 1, 2]


def test_die_stuecke_einer_folie_laufen_gleichzeitig(tmp_path):
    """A single long slide has to send its pieces in parallel, otherwise it stays slow."""
    _, tts, _ = _lauf([LANG], tmp_path)
    assert tts.anfragen > 1, "Testtext muss in mehrere Stuecke zerfallen"
    # As many at once as the provider has seats, see TTS_PROVIDER_MAX_CONCURRENT.
    assert tts.max_gleichzeitig == min(tts.anfragen, generation.resolve_tts_parallelism())


def test_der_deckel_fuer_gleichzeitige_anfragen_haelt(tmp_path, monkeypatch):
    monkeypatch.setattr(generation, "resolve_tts_parallelism", lambda: 4)
    _, tts, _ = _lauf([LANG] * 3, tmp_path)
    assert tts.max_gleichzeitig <= 4


def test_die_stuecke_werden_in_textreihenfolge_zusammengesetzt(tmp_path):
    """Swapped pieces would tear the sentence structure of the slide apart."""

    class NummerierendesTts:
        def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
            return {"audio_bytes": text[:8].encode(), "alignment": None}

        # Longer pieces take longer so the order is not right by accident.

    tts = NummerierendesTts()
    gemeldet: list[int] = []
    ergebnis = asyncio.run(generate_all_tts(
        [LANG], tts, tmp_path, 1.0, voice_id="alloy",
        on_slide_done=lambda current, total, folie: gemeldet.append(folie),
    ))
    from src.services.openai_compat_tts import _split_text
    erwartet = b"".join(s[:8].encode() for s in _split_text(LANG))
    assert ergebnis[0][0].read_bytes() == erwartet


def test_jede_folie_meldet_sich_genau_einmal(tmp_path):
    gemeldet, _, _ = _lauf([LANG, KURZ, LANG], tmp_path)
    assert sorted(gemeldet) == [0, 1, 2]
    assert len(gemeldet) == 3
