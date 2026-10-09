"""A partial failure is redone individually, not the whole batch."""
from src.services.llm_translation_client import LLMTranslationClient


def _client():
    # Construction does no network I/O (OpenAI client is lazy).
    return LLMTranslationClient(api_key="k", base_url="http://x/v1", model="m", provider="test")


def test_parse_numbered_clean():
    raw = "1. Bonjour\n2. Le temps est beau\n3. J'apprends"
    results, missing = LLMTranslationClient._parse_numbered(raw, 3)
    assert results == ["Bonjour", "Le temps est beau", "J'apprends"]
    assert missing == []


def test_parse_numbered_missing_middle():
    raw = "1. A\n3. C"  # model dropped item 2
    results, missing = LLMTranslationClient._parse_numbered(raw, 3)
    assert results == ["A", None, "C"]
    assert missing == [1]


def test_parse_numbered_is_keyed_by_number_not_position():
    # Even though only two lines are present, alignment must follow the numbers.
    raw = "2. deux\n4. quatre"
    results, missing = LLMTranslationClient._parse_numbered(raw, 4)
    assert results == [None, "deux", None, "quatre"]
    assert missing == [0, 2]


def test_parse_numbered_multiline_item():
    raw = "1. erste Zeile\nnoch dazu\n2. zweite"
    results, missing = LLMTranslationClient._parse_numbered(raw, 2)
    assert results == ["erste Zeile\nnoch dazu", "zweite"]
    assert missing == []


def test_parse_numbered_unparseable():
    results, missing = LLMTranslationClient._parse_numbered("model returned prose, no list", 3)
    assert results == [None, None, None]
    assert missing == [0, 1, 2]


def test_translate_chunk_partial_list_redoes_the_whole_chunk(monkeypatch):
    # A short list means the model renumbered its own paragraphs, so its numbers lie.
    c = _client()
    monkeypatch.setattr(c, "_completion_with_retry", lambda system, user, **kw: ("1. A\n3. C", "stop"))
    seen = {}

    def fake_each(texts, src, tgt):
        seen["texts"] = list(texts)
        return [f"FIX:{t}" for t in texts]

    monkeypatch.setattr(c, "_translate_each", fake_each)
    out = c._translate_chunk(["a", "b", "c"], "German", "French")
    assert out == ["FIX:a", "FIX:b", "FIX:c"]
    assert seen["texts"] == ["a", "b", "c"]


def test_zusammengefasste_antwort_verschiebt_nichts(monkeypatch):
    """The reported bug: 20 lines came back as 10 merged paragraphs."""
    c = _client()
    quellen = [f"satz {i}" for i in range(1, 21)]
    verschmolzen = "\n".join(f"{i}. absatz {i}" for i in range(1, 11))
    monkeypatch.setattr(c, "_completion_with_retry", lambda system, user, **kw: (verschmolzen, "stop"))
    monkeypatch.setattr(c, "_translate_each", lambda texts, src, tgt: [f"EN:{t}" for t in texts])
    out = c._translate_chunk(quellen, "German", "English")
    assert out == [f"EN:{t}" for t in quellen]


def test_translate_chunk_unparseable_falls_back_whole(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_completion_with_retry", lambda system, user, **kw: ("garbage, no numbers", "stop"))
    seen = {}

    def fake_each(texts, src, tgt):
        seen["texts"] = list(texts)
        return [t.upper() for t in texts]

    monkeypatch.setattr(c, "_translate_each", fake_each)
    out = c._translate_chunk(["a", "b"], "German", "French")
    assert out == ["A", "B"]
    assert seen["texts"] == ["a", "b"]  # whole chunk per-item


def test_translate_chunk_clean_makes_no_extra_calls(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_completion_with_retry", lambda system, user, **kw: ("1. A\n2. B\n3. C", "stop"))

    def boom(*a, **k):
        raise AssertionError("_translate_each must not be called on a clean parse")

    monkeypatch.setattr(c, "_translate_each", boom)
    assert c._translate_chunk(["a", "b", "c"], "German", "French") == ["A", "B", "C"]


def test_der_schalter_gegen_das_denken_geht_mit(monkeypatch):
    from types import SimpleNamespace
    client = _client()
    client._extra_body = {"reasoning_effort": "none"}
    gesehen = {}

    def create(**kw):
        gesehen.update(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Hallo"), finish_reason="stop")],
                           usage=None, model="m")

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    monkeypatch.setattr("src.services.llm_translation_client._verbrauch", lambda *a, **k: None)
    client._completion_with_retry("s", "u")
    assert gesehen["extra_body"] == {"reasoning_effort": "none"}


def test_der_uebersetzer_bekommt_das_profil_seines_modells(monkeypatch):
    from src import database as db
    from src import dependencies
    from src.services import feature_router

    anbieter = {"id": 21, "name": "myLab", "base_url": "https://mylab.example", "enabled": True,
                "protocol": "openai_compat", "api_key": "m"}
    monkeypatch.setattr(db, "get_route", lambda f: {"provider_id": 21, "provider_models": {"21": "chat-vl-small"}})
    monkeypatch.setattr(db, "get_provider", lambda pid: anbieter)
    monkeypatch.setattr(feature_router, "_attach_model_profile",
                        lambda client, binding: setattr(client, "_extra_body", {"aus": binding.model}))
    client, _glossar = dependencies.get_translate_client_for_provider(21, feature="doc_translate")
    assert client._extra_body == {"aus": "chat-vl-small"}
