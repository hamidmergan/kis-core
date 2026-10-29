"""Every client talking to an AI provider goes through the door with seat and fallback."""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

# Probes measure one provider on purpose and must neither wait for a seat nor fall back.
_PROBES = {"services/model_limits.py"}


def _calls(name):
    for datei in SRC.rglob("*.py"):
        rel = str(datei.relative_to(SRC))
        for knoten in ast.walk(ast.parse(datei.read_text())):
            if isinstance(knoten, ast.Call):
                f = knoten.func
                if (isinstance(f, ast.Name) and f.id == name) or (isinstance(f, ast.Attribute) and f.attr == name):
                    yield rel, knoten


def _passes(knoten, keyword):
    return any(k.arg == keyword or k.arg is None for k in knoten.keywords)


def test_jeder_openai_client_bekommt_die_tuer():
    ohne = [f"{rel}:{k.lineno}" for name in ("OpenAI", "AsyncOpenAI") for rel, k in _calls(name)
            if rel not in _PROBES and not _passes(k, "http_client")]
    assert ohne == []


def test_jeder_llm_client_bekommt_die_tuer():
    ohne = [f"{rel}:{k.lineno}" for rel, k in _calls("OpenAICompatLLMClient")
            if not _passes(k, "http_client")]
    assert ohne == []


def test_der_llm_client_des_routers_hat_die_tuer(monkeypatch):
    from src.services import feature_router, provider_transport

    monkeypatch.setattr(provider_transport, "fallback_target", lambda *a, **k: None)
    monkeypatch.setattr(feature_router, "_attach_model_profile", lambda client, binding: None)
    binding = feature_router.FeatureBinding(
        feature="stt", model="whisper",
        provider={"id": 21, "name": "myLab", "base_url": "https://mylab.example", "api_key": "k",
                  "concurrency": {"stt": 3}})
    client = feature_router.make_llm_client(binding)
    tuer = client._client._client._transport
    assert isinstance(tuer, provider_transport.SdkTransport)
    assert tuer._door.bucket == "stt" and tuer._door.primary.caps == {"stt": 3}
    assert isinstance(client._async_client._client._transport, provider_transport.AsyncSdkTransport)


def test_die_uebersetzung_nimmt_ohne_wahl_die_erste_wahl_aus_dem_adminbereich(monkeypatch):
    from src import database as db
    from src import dependencies

    anbieter = {
        20: {"id": 20, "name": "GWDG", "base_url": "https://gwdg.example", "enabled": True,
             "protocol": "openai_compat", "api_key": "g"},
        21: {"id": 21, "name": "myLab", "base_url": "https://mylab.example", "enabled": True,
             "protocol": "openai_compat", "api_key": "m"},
    }
    monkeypatch.setattr(db, "get_route", lambda f: {"provider_id": 21, "provider_models": {"21": "chat-fast"}})
    monkeypatch.setattr(db, "get_provider", lambda pid: anbieter.get(pid))
    monkeypatch.setattr(dependencies, "get_translation_providers", lambda: [anbieter[20], anbieter[21]])

    client, _glossar = dependencies.get_translate_client_for_provider(None, feature="doc_translate")
    assert client._model == "chat-fast"
    assert client._client._client._transport._door.primary.provider_id == 21
