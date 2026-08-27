"""The preview has to know WHICH slide is finished, not only how many."""

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
    """Without audio the slide is still finished, otherwise the tile stays grey forever."""
    assert _nummern(["Eins.", "   ", "Drei."], tmp_path) == [0, 1, 2]


def test_fortschritt_traegt_die_fertigen_nummern_sortiert():
    assert _fortschritt_vertonung({2, 0}, 5, 2) == {
        "step": "tts", "current": 2, "total": 5, "fertig": [0, 2], "nicht_dabei": [],
    }


def test_gesprochen_zaehlt_unabhaengig_von_der_groesse_von_fertig():
    """Cached slides fill ``fertig`` right away without raising the ``gesprochen`` counter."""
    assert _fortschritt_vertonung({0, 1, 2}, 27, 1) == {
        "step": "tts", "current": 1, "total": 27, "fertig": [0, 1, 2], "nicht_dabei": [],
    }
