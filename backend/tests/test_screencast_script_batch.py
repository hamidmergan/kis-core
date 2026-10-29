"""The slide to script mapping has to hold for faulty batches too."""

import pytest

from src.services.openai_compat_llm import _scripts
from src.services.openai_compat_llm._scripts import _ScriptsMixin


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """The second attempt waits 5 seconds in operation, not in the test."""
    monkeypatch.setattr(_scripts, "_BATCH_RETRY_DELAY", 0.0)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls: list[list[dict]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        reply = self._replies.pop(0) if self._replies else "..."
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)


class FakeClient:
    def __init__(self, replies):
        self.chat = type("Chat", (), {"completions": FakeCompletions(replies)})()


class ScriptClient(_ScriptsMixin):
    """Only the script logic, without a real provider."""

    def __init__(self, replies, batch_size=3):
        self._client = FakeClient(replies)
        self._model = "test-model"
        self._extra_body = {}
        self._batch_size = batch_size
        self._batch_max_workers = 1
        self._batch_timeout = 5.0

    @property
    def calls(self):
        return self._client.chat.completions.calls


def _slides(n: int) -> list[str]:
    return [f"Folientext {i + 1}" for i in range(n)]


def test_clean_batch_maps_one_to_one():
    client = ScriptClient(["Skript A\n|||\nSkript B\n|||\nSkript C"])
    scripts = client.generate_scripts_batch(_slides(3), add_greeting=False, add_closing=False)
    assert scripts == ["Skript A", "Skript B", "Skript C"]


def test_trailing_delimiter_is_tolerated():
    """A separator at the end is harmless and must not count as an error."""
    client = ScriptClient(["Skript A\n|||\nSkript B\n|||\nSkript C\n|||"])
    scripts = client.generate_scripts_batch(_slides(3), add_greeting=False, add_closing=False)
    assert scripts == ["Skript A", "Skript B", "Skript C"]


def test_missing_delimiter_falls_back_to_one_call_per_slide():
    """Instead of shifting, every slide is generated individually, which cannot go wrong."""
    client = ScriptClient([
        "Skript A und Skript B zusammen\n|||\nSkript C",  # one separator short
        "Skript A und Skript B zusammen\n|||\nSkript C",  # retry, wrong again
        "Skript A",
        "Skript B",
        "Skript C",
    ])
    scripts = client.generate_scripts_batch(_slides(3), add_greeting=False, add_closing=False)
    assert scripts == ["Skript A", "Skript B", "Skript C"]


def test_failed_single_slide_only_costs_that_slide():
    """If a slide fails in individual mode it stays empty, the others do not."""
    client = ScriptClient([
        "nur ein Teil",           # batch, attempt 1
        "nur ein Teil",           # batch, attempt 2
        "Skript A",               # slide 1 alone
        RuntimeError("Anbieter weg"),  # slide 2 alone
        "Skript C",               # slide 3 alone
    ])
    scripts = client.generate_scripts_batch(_slides(3), add_greeting=False, add_closing=False)
    assert scripts[0] == "Skript A"
    assert scripts[1] == ""
    assert scripts[2] == "Skript C"


def test_short_last_batch_keeps_its_length_on_failure():
    """The last batch is often shorter, if it fails the list must not grow."""
    client = ScriptClient(
        [RuntimeError("weg")] * 20,
        batch_size=3,
    )
    scripts = client.generate_scripts_batch(_slides(4), add_greeting=False, add_closing=False)
    assert len(scripts) == 4


@pytest.mark.parametrize("count", [1, 2, 5, 8])
def test_slide_count_is_always_preserved(count):
    client = ScriptClient(["kaputte Antwort ohne Trenner"] * 40)
    scripts = client.generate_scripts_batch(_slides(count), add_greeting=False, add_closing=False)
    assert len(scripts) == count


def _rules() -> str:
    from src.services.openai_compat_llm._scripts import build_length_and_format_rules

    return build_length_and_format_rules(3, "EN-US", "", "", 1500, 2000)


def test_length_rule_is_a_ceiling_not_a_range():
    """A fixed range forces the model to repeat itself on thin slides."""
    rules = _rules()
    assert "between 1500 and 2000 characters" not in rules
    assert "Never write more than 2000 characters" in rules


def test_padding_is_forbidden_explicitly():
    rules = _rules().lower()
    assert "never repeat" in rules
    assert "stop as soon as the slide is covered" in rules


def test_short_slides_are_allowed_to_stay_short():
    assert "one line of content" in _rules()


def test_delimiter_contract_is_still_stated():
    rules = _rules()
    assert "|||" in rules
    assert "Separate the 3 scripts" in rules
