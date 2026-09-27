"""The summary runs on the chat model, with a provider choice."""


def test_get_llm_client_explicit_uses_service(monkeypatch):
    from src.tasks import general_tasks
    from src.services.feature_router import FeatureBinding

    captured = {}

    def fake_resolve_binding(feature, provider_id):
        captured["feature"] = feature
        captured["provider_id"] = provider_id
        return FeatureBinding(
            feature="chat",
            provider={"base_url": "http://llm.example.com", "name": "myLab", "api_key": "k"},
            model="chat-large",
        )

    monkeypatch.setattr("src.services.feature_provider_choices.resolve_binding", fake_resolve_binding)
    monkeypatch.setattr(
        "src.dependencies._resolve_llm_binding",
        lambda: (_ for _ in ()).throw(AssertionError("default path used")),
    )

    client = general_tasks._get_llm_client(21)
    assert captured == {"feature": "chat", "provider_id": 21}
    assert client._model == "chat-large"


def test_get_llm_client_default_uses_route(monkeypatch):
    from src.services.feature_router import FeatureBinding
    from src.tasks import general_tasks

    monkeypatch.setattr(
        "src.dependencies._resolve_llm_binding",
        lambda: FeatureBinding(feature="chat", model="qwen3-30b",
                               provider={"base_url": "http://llm.example.com", "name": "Anbieter A", "api_key": "k"}),
    )
    monkeypatch.setattr(
        "src.services.feature_provider_choices.resolve_binding",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("service used on default path")),
    )

    client = general_tasks._get_llm_client()
    assert client._model == "qwen3-30b"


async def test_summary_endpoint_delegates_to_service(monkeypatch):
    from src.routes import summary

    sentinel = {"providers": [{"id": 1, "name": "P1"}], "default_id": 1}

    async def fake_list(feature):
        assert feature == "chat"
        return sentinel

    monkeypatch.setattr(summary.feature_provider_choices, "list_reachable_choices", fake_list)

    result = await summary.list_summary_providers(_user={})
    assert result is sentinel
