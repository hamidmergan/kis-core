"""The provider always gets speed 1.0, slowing down happens locally."""

import asyncio

from src.services.screencast.generation import generate_all_tts


class FakeTts:
    def __init__(self):
        self.tempi = []

    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        self.tempi.append(speed)
        return {"audio_bytes": b"mp3", "alignment": None}


def test_anbieter_bekommt_immer_tempo_eins(tmp_path):
    tts = FakeTts()
    asyncio.run(generate_all_tts(["Ein Skript."], tts, tmp_path, 0.9, voice_id="alloy"))
    assert tts.tempi == [1.0], "0.9 beim Anbieter senkt die Tonhöhe und klingt hallig"


def test_auch_bei_schnellerem_tempo(tmp_path):
    tts = FakeTts()
    asyncio.run(generate_all_tts(["Ein Skript."], tts, tmp_path, 1.2, voice_id="alloy"))
    assert tts.tempi == [1.0]
