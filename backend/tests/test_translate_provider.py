
def _make_provider(id, name, protocol="openai_compat", api_key=None, base_url="http://example.com"):
    return {"id": id, "name": name, "protocol": protocol, "api_key": api_key,
            "base_url": base_url, "enabled": True, "voices": [], "capabilities": []}


def test_get_translation_providers_merges_translation_and_chat(monkeypatch):
    from src.dependencies import get_translation_providers
    p1 = _make_provider(1, "DeepL", protocol="deepl")
    p2 = _make_provider(2, "KISSKI", protocol="openai_compat")
    p3 = _make_provider(2, "KISSKI", protocol="openai_compat")  # duplicate, different cap

    def fake_list(cap):
        if cap == "translation":
            return [p1]
        if cap == "chat":
            return [p2, p3]
        return []

    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability", fake_list)
    result = get_translation_providers()
    ids = [p["id"] for p in result]
    assert ids == [1, 2], "should deduplicate and preserve order"


def test_get_translate_client_for_provider_deepl(monkeypatch):
    from src.dependencies import get_translate_client_for_provider
    from src.services.glossary import GlossaryService

    provider = _make_provider(5, "DeepL", protocol="deepl", api_key="secret:fx",
                              base_url="https://api-free.deepl.com")
    route = {"provider_models": {"5": ""}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(5, glossary_entries={"Hello": "Hallo"})
    from src.services.deepl_client import DeepLClient
    assert isinstance(client, DeepLClient)
    assert isinstance(glossary, GlossaryService)


def test_get_translate_client_for_provider_llm(monkeypatch):
    from src.dependencies import get_translate_client_for_provider

    provider = _make_provider(7, "KISSKI", protocol="openai_compat", api_key="key",
                              base_url="https://llm.example.com/v1")
    route = {"provider_models": {"7": "mistral-small"}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(7, glossary_entries=None)
    from src.services.llm_translation_client import LLMTranslationClient
    assert isinstance(client, LLMTranslationClient)


def test_get_translate_client_returns_none_for_missing_provider(monkeypatch):
    from src.dependencies import get_translate_client_for_provider

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: None)

    client, glossary = get_translate_client_for_provider(99)
    assert client is None


def test_get_translate_client_fallback_when_provider_id_none(monkeypatch):
    from src.dependencies import get_translation_providers, get_translate_client_for_provider

    provider = _make_provider(3, "DeepL", protocol="deepl", api_key="key")
    route = {"provider_models": {}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability",
                        lambda cap: [provider] if cap == "translation" else [])
    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(None)
    from src.services.deepl_client import DeepLClient
    assert isinstance(client, DeepLClient)


def test_get_translate_client_returns_none_for_disabled_provider(monkeypatch):
    from src.dependencies import get_translate_client_for_provider
    provider = _make_provider(10, "DeepL", protocol="deepl", api_key="key")
    provider["enabled"] = False
    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    client, glossary = get_translate_client_for_provider(10)
    assert client is None


def test_get_translate_client_returns_none_when_no_providers_available(monkeypatch):
    from src.dependencies import get_translate_client_for_provider
    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability", lambda cap: [])
    client, glossary = get_translate_client_for_provider(None)
    assert client is None
