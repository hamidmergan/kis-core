"""STT provider routing: end-user provider choice for the transcription tool.

Covers that resolve_whisper_client routes an explicit user pick through the
capability-based provider-choice service, and falls back to the admin default
route when no provider is picked. The reachability/listing logic itself lives
in test_feature_provider_choices.py.
"""


def _binding(model="whisper-large-v3"):
    from src.services.feature_router import FeatureBinding

    return FeatureBinding(
        feature="stt",
        provider={"base_url": "http://stt.example.com", "name": "Whisper", "api_key": None},
        model=model,
    )


def test_resolve_whisper_client_uses_service_for_explicit_provider(monkeypatch):
    captured = {}

    def fake_resolve_binding(feature, provider_id):
        captured["feature"] = feature
        captured["provider_id"] = provider_id
        return _binding()

    monkeypatch.setattr(
        "src.services.feature_provider_choices.resolve_binding", fake_resolve_binding
    )

    from src.dependencies import resolve_whisper_client

    client = resolve_whisper_client(7)
    assert captured == {"feature": "stt", "provider_id": 7}
    assert client._whisper_model == "whisper-large-v3"


def test_resolve_whisper_client_default_uses_route(monkeypatch):
    captured = {}

    def fake_resolve(feature, *, user_provider_id=None):
        captured["feature"] = feature
        captured["user_provider_id"] = user_provider_id
        return _binding()

    monkeypatch.setattr("src.dependencies.feature_router.resolve", fake_resolve)
    # Must NOT touch the user-choice service on the default path.
    monkeypatch.setattr(
        "src.services.feature_provider_choices.resolve_binding",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("service used on default path")),
    )

    from src.dependencies import resolve_whisper_client

    resolve_whisper_client()
    assert captured == {"feature": "stt", "user_provider_id": None}


async def test_transcription_endpoint_delegates_to_service(monkeypatch):
    from src.routes import transcription

    sentinel = {"providers": [{"id": 1, "name": "P1"}], "default_id": 1}

    async def fake_list(feature):
        assert feature == "stt"
        return sentinel

    monkeypatch.setattr(transcription.feature_provider_choices, "list_reachable_choices", fake_list)

    result = await transcription.list_transcription_providers(current_user={})
    assert result is sentinel
