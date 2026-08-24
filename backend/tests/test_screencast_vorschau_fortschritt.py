"""Die Vorschau muss wissen, WELCHE Folie fertig ist, nicht nur wie viele."""

import asyncio

from src.services.screencast.generation import generate_all_tts
from src.tasks.screencast_tasks._pipeline import _fortschritt_vertonung


class FakeTts:
    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        return {"audio_bytes": b"mp3", "alignment": None}


def _nummern(scripts, tmp_path):
    gemeldet = []
    asyncio.run(generate_all_tts(
        scripts, FakeTts(), tmp_path, 1.0, voice_id="alloy",
        on_slide_done=lambda current, total, folie: gemeldet.append(folie),
    ))
    return sorted(gemeldet)


def test_jede_fertige_folie_meldet_ihre_nummer(tmp_path):
    assert _nummern(["Eins.", "Zwei.", "Drei."], tmp_path) == [0, 1, 2]


def test_folie_ohne_text_meldet_sich_auch(tmp_path):
    """Ohne Ton ist die Folie trotzdem fertig, sonst bleibt die Kachel ewig grau."""
    assert _nummern(["Eins.", "   ", "Drei."], tmp_path) == [0, 1, 2]


def test_fortschritt_traegt_die_fertigen_nummern_sortiert():
    assert _fortschritt_vertonung([2, 0], 5) == {
        "step": "tts", "current": 2, "total": 5, "fertig": [0, 2],
    }


def test_fortschritt_zeigt_den_echten_stand_nicht_den_freigegebenen():
    """Die Freigabe haelt spaetere Folien zurueck, der Zaehler darf nicht stillstehen."""
    assert _fortschritt_vertonung([0], 27, vertont=8) == {
        "step": "tts", "current": 8, "total": 27, "fertig": [0],
    }
