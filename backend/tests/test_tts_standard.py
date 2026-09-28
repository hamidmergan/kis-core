"""Which voice the speech tools preselect: the starred provider, with the admin's default voice."""

from src.services import tts_standard

MYLAB = {"id": 21, "voices": [{"voice_id": "alloy"}, {"voice_id": "nova"}]}
KOKORO = {"id": 89, "voices": [{"voice_id": "af_heart"}, {"voice_id": "de_anna"}]}
STUMM = {"id": 5, "voices": []}


def test_der_stern_fuehrt_mit_seiner_ersten_stimme():
    assert tts_standard.standard_voice([MYLAB, KOKORO], 89, None) == (89, "af_heart")


def test_die_standardstimme_des_sternanbieters_gilt():
    assert tts_standard.standard_voice([MYLAB, KOKORO], 89, (89, "de_anna")) == (89, "de_anna")


def test_eine_standardstimme_eines_anderen_anbieters_zaehlt_nicht():
    assert tts_standard.standard_voice([MYLAB, KOKORO], 89, (21, "nova")) == (89, "af_heart")


def test_eine_verschwundene_standardstimme_faellt_auf_die_erste_zurueck():
    assert tts_standard.standard_voice([MYLAB, KOKORO], 89, (89, "weg")) == (89, "af_heart")


def test_ohne_stern_gilt_die_standardstimme():
    assert tts_standard.standard_voice([MYLAB, KOKORO], None, (89, "de_anna")) == (89, "de_anna")


def test_ist_der_sternanbieter_nicht_da_gilt_die_standardstimme():
    """An unreachable starred provider is missing from the list, the default voice still counts."""
    assert tts_standard.standard_voice([MYLAB, KOKORO], 77, (89, "de_anna")) == (89, "de_anna")


def test_ohne_stern_und_standardstimme_der_erste_anbieter():
    assert tts_standard.standard_voice([MYLAB, KOKORO], None, None) == (21, "alloy")


def test_ein_anbieter_ohne_stimmen_wird_uebersprungen():
    assert tts_standard.standard_voice([STUMM, KOKORO], 5, None) == (89, "af_heart")


def test_ohne_anbieter_gibt_es_keine_stimme():
    assert tts_standard.standard_voice([], 21, (21, "alloy")) is None


def test_der_stern_rueckt_nach_vorn_der_rest_bleibt_in_reihe():
    drei = [MYLAB, STUMM, KOKORO]
    assert [p["id"] for p in tts_standard.star_first(drei, 89)] == [89, 21, 5]
    assert [p["id"] for p in tts_standard.star_first(drei, None)] == [21, 5, 89]
