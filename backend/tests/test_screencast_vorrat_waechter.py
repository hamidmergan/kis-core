"""After a voice change no audio from the old cache may live on."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from src.routes.screencast.render import _vorrat_passt_nicht

UUID = "a" * 32


def _body(**kwargs):
    grund = {"voice_id": "anna", "provider_id": 2, "target_lang": "DE"}
    return SimpleNamespace(**{**grund, **kwargs})


def _lauf(alt_params: dict | None, alt_sprache: str, body):
    def hole(*a, **k):
        if alt_params is None:
            raise FileNotFoundError()
        return json.dumps(alt_params).encode()

    with patch("src.routes.screencast.render.get_job_file", side_effect=hole), \
         patch("src.routes.screencast.render.load_result_meta", return_value={"target_lang": alt_sprache}):
        return _vorrat_passt_nicht(1, UUID, body)


_ALT = {"dispatch_as": "render", "voice_id": "anna", "provider_id": 2}


def test_gleiche_stimme_behaelt_den_vorrat():
    assert _lauf(_ALT, "DE", _body()) is False


def test_andere_stimme_wirft_den_vorrat_weg():
    assert _lauf(_ALT, "DE", _body(voice_id="bernd")) is True


def test_anderer_anbieter_wirft_den_vorrat_weg():
    assert _lauf(_ALT, "DE", _body(provider_id=5)) is True


def test_andere_zielsprache_wirft_den_vorrat_weg():
    assert _lauf(_ALT, "DE", _body(target_lang="EN-US")) is True


def test_anderes_tempo_behaelt_den_vorrat():
    """Voicing always happens at 1.0, the speed only enters the video via atempo."""
    assert _lauf(_ALT, "DE", _body(speed=1.4)) is False


def test_ohne_frueheren_lauf_gibt_es_nichts_zu_pruefen():
    assert _lauf(None, "", _body()) is False
