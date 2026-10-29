"""Every render needs a seat at the provider, whether podcast, read-aloud or screencast."""

from src.services import openai_compat_tts, provider_transport
from src.services.feature_router import FeatureBinding

MYLAB = {"id": 21, "name": "myLab", "base_url": "https://models.mylab.example/v1", "api_key": "k",
         "enabled": True, "protocol": "openai_compat", "concurrency": {"tts": 4}}


def test_jede_vertonung_geht_durch_die_tuer_mit_dem_feld_des_anbieters():
    tts = openai_compat_tts.OpenAICompatTTSClient(
        MYLAB["base_url"], "tts-1", "k", binding=FeatureBinding(feature="tts", provider=MYLAB, model="tts-1"))
    with tts._http() as client:
        tuer = client._transport
    assert isinstance(tuer, provider_transport.ProviderTransport)
    assert tuer._door.bucket == "tts"
    assert tuer._door.primary.caps == {"tts": 4}
    # A voice only exists at its own provider, so speech output never falls back.
    assert tuer._door.fallback is None


def test_die_erreichbarkeitspruefung_nimmt_keinen_platz():
    tts = openai_compat_tts.OpenAICompatTTSClient(MYLAB["base_url"], "", "k")
    with tts._http() as client:
        assert not isinstance(client._transport, provider_transport.ProviderTransport)


def test_der_dienst_baut_den_client_mit_bindung(monkeypatch):
    from src import database as db
    from src import dependencies

    monkeypatch.setattr(db, "get_provider", lambda pid: MYLAB)
    monkeypatch.setattr(dependencies, "tts_model_for_provider", lambda pid: "tts-1")
    tts = dependencies.get_tts_client_for_provider(21)
    assert tts._binding.provider["id"] == 21 and tts._binding.feature == "tts"
