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


def test_translate_chunk_retranslates_only_missing(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_completion_with_retry", lambda system, user, **kw: ("1. A\n3. C", "stop"))
    seen = {}

    def fake_each(texts, src, tgt):
        seen["texts"] = list(texts)
        return [f"FIX:{t}" for t in texts]

    monkeypatch.setattr(c, "_translate_each", fake_each)
    out = c._translate_chunk(["a", "b", "c"], "German", "French")
    assert out == ["A", "FIX:b", "C"]
    assert seen["texts"] == ["b"]  # only the missing item, not the whole chunk


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
