"""LLM-Übersetzung in Blöcken: abgeschnittene Antworten dürfen nicht durchrutschen.

Der Client schickt bis zu 40 nummerierte Einträge in einem Aufruf. Reißt die
Antwort an der Token-Grenze ab, fehlen die letzten Einträge ganz und der
angefangene wird mitten im Satz beendet. Die fehlenden hat der Code erkannt,
den angefangenen nicht. Der galt als fertige Übersetzung und landete
abgeschnitten in der Datei.
"""

import pytest

from src.services.llm_translation_client import LLMTranslationClient


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content, finish_reason):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)
        self.batch_sizes: list[int] = []

    def create(self, **kwargs):
        user = kwargs["messages"][-1]["content"]
        self.batch_sizes.append(len([ln for ln in user.splitlines() if ln.strip()]))
        reply = self._replies.pop(0) if self._replies else ("1. rest", "stop")
        content, finish_reason = reply
        return FakeResponse(content, finish_reason)


def _client(replies) -> LLMTranslationClient:
    client = LLMTranslationClient.__new__(LLMTranslationClient)
    client._client = type("C", (), {"chat": type("Ch", (), {"completions": FakeCompletions(replies)})()})()
    client._model = "test"
    client._provider = "openai_compat"
    client._glossary = {}
    return client


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


def test_complete_answer_maps_one_to_one():
    client = _client([("1. one\n2. two\n3. three", "stop")])
    assert client.translate_batch(["eins", "zwei", "drei"], "DE", "EN") == ["one", "two", "three"]


def test_truncated_answer_is_not_taken_as_finished():
    """Die Antwort bricht in Eintrag 3 ab. Dann darf 'thr' nicht als Ergebnis gelten."""
    client = _client([
        ("1. one\n2. two\n3. thr", "length"),   # abgeschnitten in Eintrag 3
        ("1. one", "stop"),                     # erste Hälfte neu (1 Eintrag)
        ("1. two\n2. three", "stop"),           # zweite Hälfte neu (2 Einträge)
    ])
    out = client.translate_batch(["eins", "zwei", "drei"], "DE", "EN")
    assert out == ["one", "two", "three"]
    # "thr" darf nirgends überlebt haben
    assert "thr" not in out


def test_single_item_truncation_retries_with_more_room():
    """Reasoning-Modelle denken lange, bevor überhaupt etwas herauskommt.

    Gemessen an qwen3.5-122b-a10b: ein Satz mit 52 Zeichen
    verbraucht 998 Ausgabe-Token und liefert 45 Zeichen Text. Bei zu knappem
    Budget kommt finish_reason "length" und content None zurück. Teilen hilft
    da nicht, der Block ist ja schon einer. Also mehr Platz geben.
    """
    client = _client([
        ("", "length"),     # Blockaufruf, Budget zu knapp
        ("", "length"),     # Einzelaufruf, immer noch zu knapp
        ("one", "stop"),    # Einzelaufruf mit vollem Budget
    ])
    assert client.translate_batch(["eins"], "DE", "EN") == ["one"]


def test_single_item_truncation_is_reported_when_even_the_maximum_is_too_small():
    client = _client([("", "length")] * 3)
    with pytest.raises(RuntimeError):
        client.translate_batch(["ein sehr langer Text"], "DE", "EN")


def test_token_budget_leaves_room_for_thinking():
    """Ein einzelner kurzer Satz kostet an qwen3.5 rund 1000 Token, fast alles Denken."""
    assert LLMTranslationClient._max_tokens_for("1. Kurzer Satz", 1) >= 4000


def test_token_budget_covers_the_measured_six_item_case():
    """Gemessen: 6 kurze Einträge verbrauchen 6856 Ausgabe-Token."""
    numbered = "\n".join(f"{i + 1}. Ein kurzer deutscher Satz" for i in range(6))
    assert LLMTranslationClient._max_tokens_for(numbered, 6) >= 6856


def test_token_budget_grows_with_the_item_count():
    """Der Denkaufwand haengt an der Zahl der Eintraege, nicht an ihrer Laenge."""
    assert LLMTranslationClient._max_tokens_for("x" * 100, 20) > LLMTranslationClient._max_tokens_for("x" * 100, 1)


def test_token_budget_stays_within_the_cap():
    assert LLMTranslationClient._max_tokens_for("x" * 500_000, 500) <= 32768


def test_missing_items_are_retranslated_individually():
    client = _client([
        ("1. one\n3. three", "stop"),  # Eintrag 2 fehlt
        ("two", "stop"),               # Einzelabfrage
    ])
    assert client.translate_batch(["eins", "zwei", "drei"], "DE", "EN") == ["one", "two", "three"]


def test_result_length_always_matches_input():
    client = _client([("völlig anderes Format", "stop")] + [("x", "stop")] * 10)
    out = client.translate_batch(["a", "b", "c", "d"], "DE", "EN")
    assert len(out) == 4
