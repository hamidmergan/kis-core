"""Kein Skript darf auf der falschen Folie landen."""

import pytest

from src.services.openai_compat_llm import _scripts
from src.services.openai_compat_llm._scripts import _ScriptsMixin, find_misaligned


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


# Die drei Folien aus dem echten Durchlauf, gekürzt.
FOLIE_BILDER = "Sample tasks"
FOLIE_NEWSTEST = (
    "Current study by the New Responsibility Foundation on how to deal with news "
    "and information on the internet. Test subjects only achieved an average of "
    "13.3 out of a maximum of 30 points."
)
FOLIE_PROGRAMME = (
    "Numerous programs and projects, especially for children and young people and "
    "older people. Comprehensive handout from the ITU: Digital Skills Toolkit."
)

SKRIPT_NEWSTEST = (
    "A current study by the New Responsibility Foundation examines how people deal "
    "with news and information on the internet. Test subjects achieved 13.3 points."
)
SKRIPT_PROGRAMME = (
    "There are numerous programs and projects for children and young people and for "
    "older people. The ITU provides a handout called the Digital Skills Toolkit."
)
SKRIPT_BILDER = "This slide shows sample tasks on spotting advertisements in news feeds."


def test_erkennt_den_versatz_aus_dem_echten_durchlauf():
    versetzt = [SKRIPT_NEWSTEST, SKRIPT_PROGRAMME, SKRIPT_PROGRAMME]
    folien = [FOLIE_BILDER, FOLIE_NEWSTEST, FOLIE_PROGRAMME]
    assert find_misaligned(versetzt, folien) is not None


def test_passende_zuordnung_gilt_nicht_als_versatz():
    passend = [SKRIPT_BILDER, SKRIPT_NEWSTEST, SKRIPT_PROGRAMME]
    folien = [FOLIE_BILDER, FOLIE_NEWSTEST, FOLIE_PROGRAMME]
    assert find_misaligned(passend, folien) is None


def test_versetzte_gruppe_wird_folie_fuer_folie_neu_erzeugt():
    client = ScriptClient([
        f"{SKRIPT_NEWSTEST}\n|||\n{SKRIPT_PROGRAMME}\n|||\n{SKRIPT_PROGRAMME}",
        SKRIPT_BILDER,
        SKRIPT_NEWSTEST,
        SKRIPT_PROGRAMME,
    ])
    scripts = client.generate_scripts_batch(
        [FOLIE_BILDER, FOLIE_NEWSTEST, FOLIE_PROGRAMME],
        add_greeting=False, add_closing=False,
    )
    assert "sample tasks" in scripts[0].lower()
    assert "New Responsibility" in scripts[1]
    assert "Digital Skills Toolkit" in scripts[2]
    assert len(client.calls) == 4, "ein Stapel, dann drei Folien einzeln"


def test_passende_gruppe_kostet_keinen_zusatzaufruf():
    client = ScriptClient([
        f"{SKRIPT_BILDER}\n|||\n{SKRIPT_NEWSTEST}\n|||\n{SKRIPT_PROGRAMME}",
    ])
    client.generate_scripts_batch(
        [FOLIE_BILDER, FOLIE_NEWSTEST, FOLIE_PROGRAMME],
        add_greeting=False, add_closing=False,
    )
    assert len(client.calls) == 1


def test_folie_ohne_text_loest_keinen_fehlalarm_aus():
    """Eine leere Folie hat keinen Inhalt, an dem sich etwas messen ließe."""
    client = ScriptClient([
        f"{SKRIPT_NEWSTEST}\n|||\n\n|||\n{SKRIPT_PROGRAMME}",
    ])
    scripts = client.generate_scripts_batch(
        [FOLIE_NEWSTEST, "", FOLIE_PROGRAMME],
        add_greeting=False, add_closing=False,
    )
    assert scripts[1] == ""
    assert len(client.calls) == 1
