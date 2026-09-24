"""Die einstellbaren Zahlen der Werkzeuge im Adminbereich: lesen, pruefen, speichern.

Laeuft ueber den ganzen Vorrat. Traegt ein weiteres Werkzeug eine Zahl ein, ist sie
damit mitgeprueft, ohne dass hier etwas dazukommt.
"""

import pytest
from fastapi import HTTPException

from src.routes.admin import settings as admin_settings
from src.routes.admin._models import UpdateSettingsRequest
from src.services import tool_numbers as tn

_ADMIN = {"role": "admin"}


class _Body:
    """Minimal stand-in for UpdateSettingsRequest: everything None except one field."""

    def __init__(self, **kwargs):
        object.__setattr__(self, "_set", kwargs)

    def __getattr__(self, name):
        return object.__getattribute__(self, "_set").get(name)

    def model_dump(self):
        return dict(object.__getattribute__(self, "_set"))


@pytest.fixture
def store(monkeypatch):
    data: dict[str, str] = {}
    monkeypatch.setattr(admin_settings.db, "get_setting",
                        lambda key, default="": data.get(key, default))
    monkeypatch.setattr(admin_settings.db, "set_setting",
                        lambda key, value: data.__setitem__(key, value))
    return data


class TestLesen:
    async def test_jede_zahl_steht_in_der_antwort(self, store):
        antwort = await admin_settings.get_settings()
        for zahl in tn.NUMBERS:
            assert antwort[zahl.key] == zahl.default

    async def test_die_spannen_kommen_mit(self, store):
        """Damit die Oberflaeche keine Grenze noch einmal aufschreiben muss."""
        antwort = await admin_settings.get_settings()
        gemeldet = {e["key"]: e for e in antwort["tool_numbers"]}
        for zahl in tn.NUMBERS:
            assert gemeldet[zahl.key] == {"key": zahl.key, "tool": zahl.tool,
                                          "default": zahl.default,
                                          "min": zahl.smallest, "max": zahl.largest}


class TestFeldUndRecht:
    def test_jede_zahl_hat_ein_feld_am_formular(self):
        """Ohne Feld kaeme der Wert nie am Backend an."""
        for zahl in tn.NUMBERS:
            assert zahl.key in UpdateSettingsRequest.model_fields

    def test_jede_zahl_haengt_an_einem_recht(self):
        """Ohne Recht duerfte jeder mit irgendeinem Einstellungsrecht daran drehen."""
        for zahl in tn.NUMBERS:
            assert admin_settings._permission_for(zahl.key) == zahl.permission

    def test_ein_erfundenes_feld_haengt_an_keinem_recht(self):
        assert admin_settings._permission_for("gibt_es_nicht") is None


class TestSpeichern:
    @pytest.mark.parametrize("zahl", tn.NUMBERS, ids=lambda z: z.key)
    async def test_beide_enden_der_spanne_gehen_durch(self, store, zahl):
        for wert in (zahl.smallest, zahl.largest):
            await admin_settings.update_settings(_Body(**{zahl.key: wert}), _ADMIN, "de")
            assert store[zahl.key] == str(wert)

    @pytest.mark.parametrize("zahl", tn.NUMBERS, ids=lambda z: z.key)
    async def test_unter_der_spanne_wird_abgewiesen(self, store, zahl):
        with pytest.raises(HTTPException) as fehler:
            await admin_settings.update_settings(
                _Body(**{zahl.key: zahl.smallest - 1}), _ADMIN, "de")
        assert fehler.value.status_code == 400
        assert zahl.key not in store

    @pytest.mark.parametrize("zahl", tn.NUMBERS, ids=lambda z: z.key)
    async def test_ueber_der_spanne_wird_abgewiesen(self, store, zahl):
        with pytest.raises(HTTPException) as fehler:
            await admin_settings.update_settings(
                _Body(**{zahl.key: zahl.largest + 1}), _ADMIN, "de")
        assert fehler.value.status_code == 400
        assert zahl.key not in store

    async def test_die_meldung_nennt_das_feld(self, store):
        with pytest.raises(HTTPException) as fehler:
            await admin_settings.update_settings(
                _Body(summary_read_max_facts=999), _ADMIN, "de")
        assert "summary_read_max_facts" in fehler.value.detail


async def test_die_zeitgrenze_bleibt_unter_der_mauer_des_anbieters():
    """Gemessen 20.09.: myLab wirft einen Aufruf bei etwa 300 s mit einem nackten 500 weg."""
    assert tn.BY_KEY["summary_call_timeout_seconds"].largest <= 300
