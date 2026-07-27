"""Keine stumme Folie, wenn die Folie Text hat.

Beobachtet an einem echten Durchlauf: Folie 18 von 34 hatte 136 Zeichen
Folientext, bekam aber kein Skript. Grund war die Regel gegen Wiederholung,
zusammen mit einer Folie, die der vorherigen stark ähnelte. Das Modell hielt
sich für fertig und schrieb nichts.

Im fertigen Video steht so eine Folie stumm da. Aufgefallen ist es erst beim
Durchsehen, also nach Vertonung und Videobau.

Der zweite Fall aus demselben Durchlauf: das Modell schrieb wörtlich "(Empty)".
Das ist kein leerer Text, wurde also vertont. Im Video sagt die Stimme "Empty".
"""

import pytest

from src.services.openai_compat_llm import _scripts
from src.services.openai_compat_llm._scripts import _ScriptsMixin, is_blank_script


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    monkeypatch.setattr(_scripts, "_BATCH_RETRY_DELAY", 0.0)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)
        self.finish_reason = "stop"


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


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


LONG = "This slide introduces the study series and its main findings."


def test_slide_with_text_never_stays_silent():
    """Folie 2 hat Inhalt, kommt aber leer zurück. Sie wird einzeln nachgeholt."""
    client = ScriptClient([
        f"{LONG}\n|||\n\n|||\n{LONG}",   # mittlere Folie leer
        "Now we look at who the affected children turn to.",  # Nachschlag
    ])
    scripts = client.generate_scripts_batch(
        ["Folientext eins", "Folientext zwei", "Folientext drei"],
        add_greeting=False, add_closing=False,
    )
    assert scripts[1].startswith("Now we look at")
    assert len(client.calls) == 2, "genau ein Nachschlag, nicht der ganze Stapel"


def test_placeholder_is_treated_as_missing():
    """"(Empty)" ist kein Skript. Es würde sonst vorgelesen."""
    client = ScriptClient([
        f"{LONG}\n|||\n(Empty)\n|||\n{LONG}",
        "The chart shows the contact persons children choose.",
    ])
    scripts = client.generate_scripts_batch(
        ["eins", "zwei", "drei"], add_greeting=False, add_closing=False
    )
    assert "Empty" not in scripts[1]
    assert scripts[1].startswith("The chart shows")


def test_placeholder_never_reaches_the_video_even_if_retry_fails():
    """Auch der zweite Versuch bringt nur einen Platzhalter, dann lieber stumm."""
    client = ScriptClient([
        f"{LONG}\n|||\n(Empty)\n|||\n{LONG}",
        "(empty)",
    ])
    scripts = client.generate_scripts_batch(
        ["eins", "zwei", "drei"], add_greeting=False, add_closing=False
    )
    assert scripts[1] == ""


def test_truly_empty_slide_costs_no_extra_call():
    """Eine Folie ohne Text darf leer bleiben, ohne Nachfrage beim Modell."""
    client = ScriptClient([f"{LONG}\n|||\n\n|||\n{LONG}"])
    scripts = client.generate_scripts_batch(
        ["eins", "", "drei"], add_greeting=False, add_closing=False
    )
    assert scripts[1] == ""
    assert len(client.calls) == 1


def test_full_batch_is_untouched():
    client = ScriptClient([f"{LONG} A\n|||\n{LONG} B\n|||\n{LONG} C"])
    scripts = client.generate_scripts_batch(
        ["eins", "zwei", "drei"], add_greeting=False, add_closing=False
    )
    assert all(s.strip() for s in scripts)
    assert len(client.calls) == 1


@pytest.mark.parametrize("value", ["", "   ", "(Empty)", "[empty]", "-", "n/a", "(leer)", "..."])
def test_blank_detection_catches_placeholders_in_any_language(value):
    """Erkennung über die Länge, nicht über eine Wortliste. Sonst gilt es nur
    für Deutsch und Englisch, KIS läuft aber mit beliebigen Zielsprachen."""
    assert is_blank_script(value)


@pytest.mark.parametrize("value", [
    "This slide shows the results.",
    "Diese Folie zeigt die Ergebnisse.",
    "Cette diapositive montre les résultats.",
])
def test_real_sentences_are_not_blank(value):
    assert not is_blank_script(value)


def test_prompt_demands_a_script_for_every_slide_with_content():
    """Die Regel gegen Wiederholung darf nicht als Freibrief zum Schweigen gelten."""
    from src.services.openai_compat_llm._scripts import build_length_and_format_rules

    rules = build_length_and_format_rules(3, "EN-US", "", "", 1500, 2000)
    assert "at least one sentence" in rules
    assert "similar to the previous one" in rules
    assert "not a placeholder word" in rules
